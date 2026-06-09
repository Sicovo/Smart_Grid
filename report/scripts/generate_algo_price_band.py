"""Generate the price-band import comparison bar chart for Section 9.

Bins each run's imported energy (J) by the sell-price band that was in
effect when it was drawn. Uses the same trapezoidal integration over
module snapshots that the live backend uses (backend.main._bus_cost_integrate),
so the totals here match the on-rig cost endpoint.

Output: report/images/algo_price_band.png
"""

import csv
import os
import sys
from bisect import bisect_right
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = REPO_ROOT / "report" / "images"

RUNS = [
    ("Naive (test 1)", Path(r"C:/Users/lenovo/Downloads/naivealgoV4test1fixed"), "#c0392b"),
    ("Naive (test 2)", Path(r"C:/Users/lenovo/Downloads/naivealgoV4test2fixed"), "#e67e22"),
    ("Smart (test 1)", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test1fixed"), "#27ae60"),
    ("Smart (test 2)", Path(r"C:/Users/lenovo/Downloads/smartalgoV4test2fixed"), "#16a085"),
]


# Price-band edges (cents per joule). Final bin is open-ended above 100.
BAND_EDGES  = [0, 30, 70, 100, np.inf]
BAND_LABELS = ["<30", "30-70", "70-100", ">=100"]
# Use ASCII to avoid font glyph holes in mpl default
BAND_LABELS_TICK = ["<30", "30-70", "70-100", ">=100"]


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def load_grid_prices(run_dir: Path):
    """Return sorted list of (timestamp, sell_price) from grid_snapshots.csv."""
    rows = []
    with (run_dir / "grid_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                ts = parse_ts(r["timestamp"])
                sp = float(r["sell_price"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append((ts, sp))
    rows.sort(key=lambda x: x[0])
    return rows


def load_module(run_dir: Path, role: str, power_field: str):
    """Return sorted list of (timestamp, p_W) for one module role."""
    rows = []
    with (run_dir / "module_snapshots.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("role") != role:
                continue
            try:
                ts = parse_ts(r["timestamp"])
                p  = float(r[power_field] or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
            if p < 0:
                p = 0.0
            rows.append((ts, p))
    rows.sort(key=lambda x: x[0])
    return rows


def import_J_by_band(run_dir: Path, max_dt_s: float = 30.0):
    """Trapezoidal integration of grid p_import, bucketed by the sell_price
    in effect at the earlier sample of each interval. Mirrors
    backend.main._bus_cost_integrate."""
    grid_rows = load_module(run_dir, "grid", "p_import")
    price_rows = load_grid_prices(run_dir)
    if not grid_rows or not price_rows:
        return np.zeros(len(BAND_EDGES) - 1)

    price_ts = [t for t, _ in price_rows]

    def price_at(ts):
        idx = bisect_right(price_ts, ts)
        if idx == 0:
            return None
        return price_rows[idx - 1][1]

    bins = np.zeros(len(BAND_EDGES) - 1)
    for i in range(1, len(grid_rows)):
        t0, p0 = grid_rows[i - 1]
        t1, p1 = grid_rows[i]
        dt = (t1 - t0).total_seconds()
        if dt <= 0 or dt > max_dt_s:
            continue
        p_avg = 0.5 * (p0 + p1)
        if p_avg <= 0:
            continue
        e_J = p_avg * dt
        pr = price_at(t0)
        if pr is None:
            continue
        for b in range(len(BAND_EDGES) - 1):
            if BAND_EDGES[b] <= pr < BAND_EDGES[b + 1]:
                bins[b] += e_J
                break
    return bins


def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    per_run = []
    for label, path, color in RUNS:
        bins = import_J_by_band(path)
        print(f"{label:>18}: {dict(zip(BAND_LABELS, [round(x, 1) for x in bins]))}  total={bins.sum():.1f} J")
        per_run.append((label, bins, color))

    x = np.arange(len(BAND_LABELS_TICK))
    width = 0.18

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for i, (label, bins, color) in enumerate(per_run):
        offset = (i - (len(per_run) - 1) / 2) * width
        ax.bar(x + offset, bins, width, label=label, color=color, edgecolor="black", lw=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(BAND_LABELS_TICK)
    ax.set_xlabel("Sell-price band when energy was imported (cents/J)")
    ax.set_ylabel("Imported energy (J)")
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_title("Where each algorithm spent its import allowance", fontsize=11, weight="bold")
    fig.tight_layout()

    out = IMAGE_DIR / "algo_price_band.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
