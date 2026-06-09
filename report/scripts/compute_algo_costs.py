"""Compute import/export energy and cost per run, matching the backend's
_day_cost_block exactly so the report's numbers and bar-chart agree with
the live /algo/run/cost endpoint.

Methodology (mirrors backend/main.py:_day_cost_block + _bus_cost_integrate):
  1. Load grid_snapshots (per-tick prices, timestamps).
  2. Window module snapshots to [first grid_ts, last grid_ts]. This drops
     the algorithm warm-up samples taken before the first Azure tick
     reached the database, and any cool-down samples after the run was
     stopped — exactly what /algo/run/cost reports.
  3. Trapezoidal: for each consecutive (r0, r1) pair, dt <= 30 s,
     p_avg = 0.5*(p0+p1) clipped at 0, energy_J = p_avg * dt,
     cost = energy_J * price-at(r0.timestamp).
  4. Bucket import energy by sell-price band for the bar chart, so the
     bar totals add up to the table's import_J.
"""

import csv
import sys
from bisect import bisect_right
from datetime import datetime
from pathlib import Path

import numpy as np


csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


REPO_ROOT = Path(__file__).resolve().parents[2]

RUNS = [
    ("Naive (test 1)", Path(r"C:/Users/lenovo/Downloads/naivealgoV4test1fixed")),
    ("Naive (test 2)", Path(r"C:/Users/lenovo/Downloads/naivealgoV4test2fixed")),
    ("Smart (test 1)", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test1fixed")),
    ("Smart (test 2)", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test2fixed")),
]

BAND_EDGES  = [0, 30, 70, 100, np.inf]
BAND_LABELS = ["<30", "30-70", "70-100", ">=100"]
MAX_DT_S    = 30.0


def parse_ts(s): return datetime.fromisoformat(s)


def load_grid(run_dir):
    """Return sorted list of (timestamp, sell, buy) and the (t_start, t_end)
    window for the FIXED-SCENARIO day only.

    The lab run actually contains TWO Azure days: a few tail ticks of the
    real Azure feed before the fixed shim activated, and then 60 ticks of
    the fixed scenario (Azure day numbers 4..7 — small integers, distinct
    from the live-feed days which are 7-digit). The dashboard's
    /algo/run/cost endpoint groups by day and shows the last-seen day as
    "today" with the rest as "previous_day". We want only "today"."""
    by_day = {}
    with (run_dir / "grid_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                ts  = parse_ts(r["timestamp"])
                day = int(r["day"])
                rows = by_day.setdefault(day, [])
                rows.append((ts, float(r["sell_price"]), float(r["buy_price"])))
            except (KeyError, TypeError, ValueError):
                continue
    if not by_day:
        return [], (None, None)
    # Pick the fixed-scenario day: 60 ticks of small day-id. In practice
    # this is the day with the most ticks (the tail-day usually has 2..8).
    target_day = max(by_day.keys(), key=lambda d: len(by_day[d]))
    rows = sorted(by_day[target_day], key=lambda x: x[0])
    return rows, (rows[0][0], rows[-1][0])


def load_module(run_dir, role, power_field, window):
    """Return sorted list of (timestamp, p_W) for one role, windowed to
    [t_start, t_end] just like backend._day_cost_block does."""
    t_start, t_end = window
    rows = []
    with (run_dir / "module_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("role") != role:
                continue
            try:
                ts = parse_ts(r["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue
            if t_start is not None and not (t_start <= ts <= t_end):
                continue
            try:
                p = float(r[power_field] or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
            if p < 0:
                p = 0.0
            rows.append((ts, p))
    rows.sort(key=lambda x: x[0])
    return rows


def integrate(mod_rows, price_rows, price_idx, by_band=False):
    """Trapezoidal: returns (energy_J, cost_raw, bands_J).
    bands_J is a per-band breakdown of energy (matches the bar-chart bins).
    price_idx is 1 for sell, 2 for buy."""
    bands = np.zeros(len(BAND_EDGES) - 1)
    total_e = 0.0
    total_c = 0.0
    if len(mod_rows) < 2 or len(price_rows) < 1:
        return 0.0, 0.0, bands

    price_ts = [r[0] for r in price_rows]

    def price_at(ts):
        idx = bisect_right(price_ts, ts)
        if idx == 0:
            return None
        return price_rows[idx - 1][price_idx]

    for i in range(1, len(mod_rows)):
        t0, p0 = mod_rows[i - 1]
        t1, p1 = mod_rows[i]
        dt = (t1 - t0).total_seconds()
        if dt <= 0 or dt > MAX_DT_S:
            continue
        p_avg = 0.5 * (p0 + p1)
        if p_avg <= 0:
            continue
        e_j = p_avg * dt
        total_e += e_j
        pr = price_at(t0)
        if pr is None:
            continue
        total_c += e_j * pr
        if by_band:
            # Bucket by sell-price band even when integrating export, so the
            # caller can choose: for the bar chart we pass price_idx=1 (sell).
            for b in range(len(BAND_EDGES) - 1):
                if BAND_EDGES[b] <= pr < BAND_EDGES[b + 1]:
                    bands[b] += e_j
                    break
    return total_e, total_c, bands


def main():
    print(f"{'Run':<20} {'Imp J':>8} {'Imp ¢':>10} {'Exp J':>8} {'Exp ¢':>10} {'Net ¢':>10}")
    print("-" * 70)
    band_table = {}
    for label, path in RUNS:
        prices, window = load_grid(path)
        grid_mod   = load_module(path, "grid",   "p_import", window)
        export_mod = load_module(path, "export", "p_dissip", window)
        imp_e, imp_c, imp_bands = integrate(grid_mod,   prices, price_idx=1, by_band=True)
        exp_e, exp_c, _         = integrate(export_mod, prices, price_idx=2, by_band=False)
        net = imp_c - exp_c
        band_table[label] = imp_bands
        print(f"{label:<20} {imp_e:>8.1f} {imp_c:>10.0f} {exp_e:>8.1f} {exp_c:>10.0f} {net:>10.0f}")

    print()
    print(f"{'Run':<20} " + " ".join(f"{b:>10}" for b in BAND_LABELS) + f" {'total':>10}")
    print("-" * 80)
    for label, _ in RUNS:
        b = band_table[label]
        print(f"{label:<20} " + " ".join(f"{x:>10.1f}" for x in b) + f" {b.sum():>10.1f}")

    # Cap cycling: integrate signed p_cap from the cap module snapshots over the
    # windowed run, splitting into charge (p_cap > 0 from grid -> cap) and
    # discharge (p_cap < 0). p_cap on the cap row is signed bus-side power.
    print()
    print(f"{'Run':<20} {'Cap chg J':>10} {'Cap dis J':>10}")
    print("-" * 45)
    for label, path in RUNS:
        prices, window = load_grid(path)
        t_start, t_end = window
        rows = []
        with (path / "module_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("role") != "cap":
                    continue
                try:
                    ts = parse_ts(r["timestamp"])
                except (KeyError, TypeError, ValueError):
                    continue
                if t_start is not None and not (t_start <= ts <= t_end):
                    continue
                try:
                    p = float(r.get("p_cap") or 0.0)
                except (TypeError, ValueError):
                    continue
                rows.append((ts, p))
        rows.sort(key=lambda x: x[0])
        chg = dis = 0.0
        for i in range(1, len(rows)):
            t0, p0 = rows[i - 1]
            t1, p1 = rows[i]
            dt = (t1 - t0).total_seconds()
            if dt <= 0 or dt > MAX_DT_S:
                continue
            p_avg = 0.5 * (p0 + p1)
            e = p_avg * dt
            if e > 0:
                chg += e
            else:
                dis += -e
        print(f"{label:<20} {chg:>10.1f} {dis:>10.1f}")


if __name__ == "__main__":
    main()
