import os
import time
import json
import requests
from pprint import pprint
from pathlib import Path
from db import GridSnapshot, SessionLocal, init_db, save_snapshot, save_module_snapshot
from concurrent.futures import ThreadPoolExecutor
from test_profile import (
    TEST_DEMAND_CYCLE,
    TEST_DEMAND_PERIOD_TICKS,
    TEST_TICK_SECONDS,
    TEST_SUN_CYCLE,
)

AZURE_BASE_URL = "https://icelec50015.azurewebsites.net"
AZURE_REQUEST_TIMEOUT = float(os.getenv("AZURE_REQUEST_TIMEOUT", "5"))
# Poll interval: 1 s so tick detection latency is bounded by 1 s instead of
# aliasing against the 5 s Azure tick. At 2 s, decisions arrive at irregular
# 4 s / 6 s spacing depending on phase. At 1 s, they land at consistent ~5 s.
MODULE_POLL_INTERVAL = float(os.getenv("MODULE_POLL_INTERVAL", "1"))
TEST_MODE_STATE_FILE = Path(__file__).with_name("poller_test_mode.json")

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


def _read_test_mode_enabled():
    try:
        payload = json.loads(TEST_MODE_STATE_FILE.read_text(encoding="utf-8"))
        return bool(payload.get("enabled", False))
    except Exception:
        return False


def _latest_day_in_db(default=-1):
    db = SessionLocal()
    try:
        row = db.query(GridSnapshot.day).order_by(GridSnapshot.id.desc()).first()
        if row is None or row[0] is None:
            return default
        return int(row[0])
    except Exception:
        return default
    finally:
        db.close()


def _build_test_grid_state(cycle_index, day_base):
    index = cycle_index % TEST_DEMAND_PERIOD_TICKS
    sample = TEST_DEMAND_CYCLE[index]
    return {
        "day": day_base + (cycle_index // TEST_DEMAND_PERIOD_TICKS),
        "tick": sample["tick"],
        "sun": float(TEST_SUN_CYCLE[index]),
        "buy_price": sample["buy_price"],
        "sell_price": sample["sell_price"],
        "instant_demand": sample["demand"],
        "deferables": [],
    }


# Module telemetry is now pushed by each board; no /tlm polling code remains.

if __name__ == "__main__":
    init_db()
    print("Grid source:", AZURE_BASE_URL)
    print("Module telemetry push mode enabled; /tlm polling disabled")

    last_day = None
    last_tick = None
    test_cycle_pos = 0
    test_mode_prev = None
    test_day_base = 0

    while True:
        try:
            test_mode_enabled = _read_test_mode_enabled()

            if test_mode_enabled != test_mode_prev:
                mode = "TEST(60-tick replay)" if test_mode_enabled else "LIVE(Azure)"
                print(f"[poller] source mode -> {mode}")
                if test_mode_enabled:
                    test_cycle_pos = 0
                    test_day_base = _latest_day_in_db(default=-1) + 1
                test_mode_prev = test_mode_enabled

            if test_mode_enabled:
                grid_state = _build_test_grid_state(test_cycle_pos, test_day_base)
                test_cycle_pos += 1
            else:
                demand = get_json(AZURE_BASE_URL + "/demand", AZURE_REQUEST_TIMEOUT)
                day = demand["day"]
                tick = demand["tick"]
                if (day, tick) == (last_day, last_tick):
                    time.sleep(MODULE_POLL_INTERVAL)
                    continue
                grid_state = build_grid_state_from_demand(demand)

            saved = save_snapshot(grid_state)
            if saved:
                print("\n=== SAVED GRID STATE ===")
                pprint(grid_state)

            last_day, last_tick = grid_state["day"], grid_state["tick"]

        except Exception as e:
            print("GRID ERROR:", e)

        # Module telemetry is delivered by board push; no polling here.
        sleep_s = TEST_TICK_SECONDS if test_mode_enabled else MODULE_POLL_INTERVAL
        time.sleep(sleep_s)
