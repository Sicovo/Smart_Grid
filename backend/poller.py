import os
import time
import requests
from pprint import pprint
from db import init_db, save_snapshot, save_module_snapshot
from concurrent.futures import ThreadPoolExecutor

AZURE_BASE_URL = "https://icelec50015.azurewebsites.net"
AZURE_REQUEST_TIMEOUT = float(os.getenv("AZURE_REQUEST_TIMEOUT", "5"))
# Poll interval: 1 s so tick detection latency is bounded by 1 s instead of
# aliasing against the 5 s Azure tick. At 2 s, decisions arrive at irregular
# 4 s / 6 s spacing depending on phase. At 1 s, they land at consistent ~5 s.
MODULE_POLL_INTERVAL = float(os.getenv("MODULE_POLL_INTERVAL", "1"))

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


# Module telemetry is now pushed by each board; no /tlm polling code remains.

if __name__ == "__main__":
    init_db()
    print("Grid source:", AZURE_BASE_URL)
    print("Module telemetry push mode enabled; /tlm polling disabled")

    last_day = None
    last_tick = None

    while True:
        try:
            demand = get_json(AZURE_BASE_URL + "/demand", AZURE_REQUEST_TIMEOUT)

            day = demand["day"]
            tick = demand["tick"]

            if (day, tick) != (last_day, last_tick):
                grid_state = build_grid_state_from_demand(demand)
                saved = save_snapshot(grid_state)

                if saved:
                    print("\n=== SAVED GRID STATE ===")
                    pprint(grid_state)

                last_day, last_tick = day, tick

        except Exception as e:
            print("GRID ERROR:", e)

        # Module telemetry is delivered by board push; no polling here.
        time.sleep(MODULE_POLL_INTERVAL)
