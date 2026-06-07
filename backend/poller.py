import json
import os
import time
import requests
from pprint import pprint
from pathlib import Path
from db import (
    get_latest_grid_tick,
    init_db,
    save_module_snapshot,
    save_snapshot,
)
from concurrent.futures import ThreadPoolExecutor

AZURE_BASE_URL = "https://icelec50015.azurewebsites.net"
AZURE_REQUEST_TIMEOUT = float(os.getenv("AZURE_REQUEST_TIMEOUT", "5"))
FIXED_TICK_INTERVAL = float(os.getenv("FIXED_TICK_INTERVAL", "5"))
# Poll interval: 1 s so tick detection latency is bounded by 1 s instead of
# aliasing against the 5 s Azure tick. At 2 s, decisions arrive at irregular
# 4 s / 6 s spacing depending on phase. At 1 s, they land at consistent ~5 s.
MODULE_POLL_INTERVAL = float(os.getenv("MODULE_POLL_INTERVAL", "1"))
BACKEND_DIR = Path(__file__).resolve().parent
FIXED_DATA_PATH = BACKEND_DIR / "fixed_grid_data.json"
CONTROL_PATH = BACKEND_DIR / "poller_control.json"
STATUS_PATH = BACKEND_DIR / "poller_status.json"

# All module telemetry is now push-based. No polling of /tlm endpoints.


def get_json(url, timeout):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def build_grid_state_from_demand(demand):
    urls = {
        "sun": AZURE_BASE_URL + "/sun",
        "price": AZURE_BASE_URL + "/price",
        "deferables": AZURE_BASE_URL + "/deferables",
    }

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            name: ex.submit(get_json, url, AZURE_REQUEST_TIMEOUT)
            for name, url in urls.items()
        }
        results = {name: fut.result() for name, fut in futures.items()}

    sun = results["sun"]
    price = results["price"]
    deferables = results["deferables"]

    return {
        "day": demand["day"],
        "tick": demand["tick"],
        "sun": sun["sun"],
        "buy_price": price["buy_price"],
        "sell_price": price["sell_price"],
        "instant_demand": demand["demand"],
        "deferables": deferables,
    }


def load_fixed_data():
    with FIXED_DATA_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data.get("ticks"), list) or not data["ticks"]:
        raise ValueError("fixed_grid_data.json must contain a non-empty ticks list")
    if len(data.get("sun_by_tick", [])) != len(data["ticks"]):
        raise ValueError("sun_by_tick must contain one value for every fixed tick")
    return data


def build_grid_state_from_fixed(fixed_data, index, run_day):
    item = fixed_data["ticks"][index]
    return {
        "day": run_day,
        "tick": item["tick"],
        "sun": fixed_data["sun_by_tick"][index],
        "buy_price": item["buy_price"],
        "sell_price": item["sell_price"],
        "instant_demand": item["demand"],
        "deferables": fixed_data.get("deferables", []),
    }


def read_control():
    try:
        with CONTROL_PATH.open("r", encoding="utf-8") as handle:
            control = json.load(handle)
        if control.get("mode") in {"azure", "fixed"}:
            return control
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"mode": "azure", "generation": "default", "run_day": None}


def write_status(payload):
    temp_path = STATUS_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    temp_path.replace(STATUS_PATH)


# Module telemetry is now pushed by each board; no /tlm polling code remains.

if __name__ == "__main__":
    init_db()
    print("Grid source:", AZURE_BASE_URL)
    print("Module telemetry push mode enabled; /tlm polling disabled")
    fixed_data = load_fixed_data()

    last_day = None
    last_tick = None
    active_generation = None
    fixed_index = 0
    next_fixed_at = 0.0

    while True:
        try:
            control = read_control()
            mode = control["mode"]
            generation = str(control.get("generation", "default"))

            if generation != active_generation:
                active_generation = generation
                next_fixed_at = 0.0
                last_day = None
                last_tick = None
                if mode == "fixed":
                    run_day = int(control["run_day"])
                    latest_fixed_tick = get_latest_grid_tick(run_day)
                    fixed_index = (
                        0 if latest_fixed_tick is None else latest_fixed_tick + 1
                    )
                    write_status({
                        "mode": "fixed",
                        "generation": generation,
                        "run_day": run_day,
                        "tick": latest_fixed_tick,
                        "index": fixed_index,
                        "total": len(fixed_data["ticks"]),
                        "completed": fixed_index >= len(fixed_data["ticks"]),
                        "updated_at": time.time(),
                    })
                else:
                    fixed_index = 0
                print(f"Poller mode changed to {mode}")

            if mode == "fixed":
                run_day = int(control["run_day"])
                now = time.monotonic()
                total = len(fixed_data["ticks"])

                if fixed_index < total and now >= next_fixed_at:
                    grid_state = build_grid_state_from_fixed(
                        fixed_data, fixed_index, run_day
                    )
                    saved = save_snapshot(grid_state)
                    if saved:
                        print("\n=== SAVED FIXED GRID STATE ===")
                        pprint(grid_state)

                    fixed_index += 1
                    next_fixed_at = now + FIXED_TICK_INTERVAL
                    write_status({
                        "mode": "fixed",
                        "generation": generation,
                        "run_day": run_day,
                        "tick": grid_state["tick"],
                        "index": fixed_index,
                        "total": total,
                        "completed": fixed_index >= total,
                        "updated_at": time.time(),
                    })
            else:
                demand = get_json(
                    AZURE_BASE_URL + "/demand", AZURE_REQUEST_TIMEOUT
                )
                day = demand["day"]
                tick = demand["tick"]

                if (day, tick) != (last_day, last_tick):
                    grid_state = build_grid_state_from_demand(demand)
                    saved = save_snapshot(grid_state)

                    if saved:
                        print("\n=== SAVED GRID STATE ===")
                        pprint(grid_state)

                    last_day, last_tick = day, tick
                    write_status({
                        "mode": "azure",
                        "generation": generation,
                        "day": day,
                        "tick": tick,
                        "completed": False,
                        "updated_at": time.time(),
                    })

        except Exception as e:
            print("GRID ERROR:", e)

        # Module telemetry is delivered by board push; no polling here.
        time.sleep(MODULE_POLL_INTERVAL)
