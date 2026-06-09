"""Total bus throughput per smart run for the Pico-overhead comparison.

Sums every energy flow that passes through the rig over one Azure day:
  - PV panel-side energy (before boost-converter loss)
  - Supercapacitor BOTH directions (charge + discharge, bus-side)
  - Grid import (bus-side)
  - Grid export (bus-side)
  - LED Load dissipation (bus-side)

All integrals are trapezoidal over consecutive module snapshots, windowed
to the fixed-scenario Azure day exactly like the dashboard's cost endpoint.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


RUNS = [
    ("Smart test 1", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test1fixed")),
    ("Smart test 2", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test2fixed")),
]

MAX_DT_S = 30.0


def parse_ts(s): return datetime.fromisoformat(s)


def fixed_day_window(run_dir):
    """Return (t_start, t_end) of the fixed-scenario day in this run."""
    by_day = {}
    with (run_dir / "grid_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                day = int(r["day"])
                ts  = parse_ts(r["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue
            by_day.setdefault(day, []).append(ts)
    target = max(by_day, key=lambda d: len(by_day[d]))
    rows = sorted(by_day[target])
    return rows[0], rows[-1]


def integrate_field(run_dir, role, field, window, *, signed=False, both_ways=False):
    """Trapezoidal integration of a single module-row field, windowed.

    signed=False clips negative samples to 0 (matches backend behaviour
    for p_import / p_dissip).
    both_ways=True separates positive and negative contributions and
    returns (pos_J, neg_J) — for p_cap where + means charge into cap and
    - means discharge to bus.
    """
    t_start, t_end = window
    rows = []
    with (run_dir / "module_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("role") != role:
                continue
            try:
                ts = parse_ts(r["timestamp"])
                p  = float(r[field] or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
            if not (t_start <= ts <= t_end):
                continue
            if not signed and not both_ways and p < 0:
                p = 0.0
            rows.append((ts, p))
    rows.sort(key=lambda x: x[0])
    if both_ways:
        pos = neg = 0.0
        for i in range(1, len(rows)):
            t0, p0 = rows[i - 1]
            t1, p1 = rows[i]
            dt = (t1 - t0).total_seconds()
            if dt <= 0 or dt > MAX_DT_S:
                continue
            p_avg = 0.5 * (p0 + p1)
            e = p_avg * dt
            if e > 0:
                pos += e
            elif e < 0:
                neg += -e
        return pos, neg
    total = 0.0
    for i in range(1, len(rows)):
        t0, p0 = rows[i - 1]
        t1, p1 = rows[i]
        dt = (t1 - t0).total_seconds()
        if dt <= 0 or dt > MAX_DT_S:
            continue
        p_avg = 0.5 * (p0 + p1)
        if not signed and p_avg <= 0:
            continue
        total += p_avg * dt
    return total


def led_dispatched(run_dir, window):
    """LED bus-side dispatched energy. The LED module reports p_dissip (the
    actual resistor dissipation) under role='load'. Integrate that."""
    t_start, t_end = window
    rows = []
    with (run_dir / "module_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("role") != "led":
                continue
            try:
                ts = parse_ts(r["timestamp"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (t_start <= ts <= t_end):
                continue
            # LED module reports per-channel power; total is red+yel+grn
            try:
                p_r = float(r.get("p_red")  or 0.0)
                p_y = float(r.get("p_yel")  or 0.0)
                p_g = float(r.get("p_grn")  or 0.0)
            except (TypeError, ValueError):
                continue
            p = max(0.0, p_r + p_y + p_g)
            rows.append((ts, p))
    rows.sort(key=lambda x: x[0])
    total = 0.0
    for i in range(1, len(rows)):
        t0, p0 = rows[i - 1]
        t1, p1 = rows[i]
        dt = (t1 - t0).total_seconds()
        if dt <= 0 or dt > MAX_DT_S:
            continue
        p_avg = 0.5 * (p0 + p1)
        if p_avg <= 0:
            continue
        total += p_avg * dt
    return total


def main():
    PICO_W = 0.262 * 5

    print(f"{'Run':<14} {'PV pnl':>8} {'CapChg':>8} {'CapDis':>8} {'Import':>8} {'Export':>8} {'LED':>8} {'Total J':>10} {'Avg W':>8}")
    print("-" * 90)
    totals = []
    for label, path in RUNS:
        win = fixed_day_window(path)
        pv  = integrate_field(path, "pv",     "p_panel",  win)
        cap_chg, cap_dis = integrate_field(path, "cap", "p_cap", win, both_ways=True)
        imp = integrate_field(path, "grid",   "p_import", win)
        exp = integrate_field(path, "export", "p_dissip", win)
        led = led_dispatched(path, win)
        total_J = pv + cap_chg + cap_dis + imp + exp + led
        avg_W   = total_J / 300.0
        totals.append((label, pv, cap_chg, cap_dis, imp, exp, led, total_J, avg_W))
        print(f"{label:<14} {pv:>8.1f} {cap_chg:>8.1f} {cap_dis:>8.1f} {imp:>8.1f} {exp:>8.1f} {led:>8.1f} {total_J:>10.1f} {avg_W:>6.2f} W")

    avg_total = sum(t[7] for t in totals) / len(totals)
    avg_avgW  = avg_total / 300.0
    print("-" * 90)
    print(f"{'Average':<14} {'':>8} {'':>8} {'':>8} {'':>8} {'':>8} {'':>8} {avg_total:>10.1f} {avg_avgW:>6.2f} W")
    print()
    pico_pct_strict = PICO_W / (PICO_W + avg_avgW) * 100
    pico_pct_loose  = PICO_W / avg_avgW * 100
    print(f"Pico aux:           1.31 W (5 x 0.262 W)")
    print(f"Avg throughput:     {avg_avgW:.3f} W")
    print(f"Pico / (Pico+Tput): {pico_pct_strict:.1f}%")
    print(f"Pico / Tput:        {pico_pct_loose:.1f}%")


if __name__ == "__main__":
    main()
