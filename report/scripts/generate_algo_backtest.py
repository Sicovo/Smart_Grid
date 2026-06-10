"""Backtest Smart V1 vs the naive baseline over all 1000 generated days
in datasets.json and plot the distribution of per-day net-cost savings.

Both policies are replayed through backtest/harness.py, which applies the
same physical model as the firmware (PV from the deterministic sun profile,
supercapacitor with 0.25%/tick leakage and 90% SMPS efficiency each way,
9 W LED clamp, droop closing the bus balance, unmet-deferrable penalty at
the day's mean sell price).

Output:
  report/images/algo_backtest_hist.png
  prints summary statistics for the report table
"""

import json
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = REPO_ROOT / "report" / "images"
sys.path.insert(0, str(REPO_ROOT))

from backtest.harness import replay                      # noqa: E402
from buysellalgorithm import naive, smart_v1             # noqa: E402


def main():
    with open(REPO_ROOT / "datasets.json") as f:
        days = json.load(f)
    print(f"loaded {len(days)} days")

    savings = []
    naive_total = smart_total = 0.0
    for i, day in enumerate(days):
        rn = replay(day, naive.decide, f"d{i}_naive")
        rs = replay(day, smart_v1.decide, f"d{i}_smart")
        naive_total += rn.net_cost
        smart_total += rs.net_cost
        savings.append(100.0 * (rn.net_cost - rs.net_cost) / rn.net_cost)

    savings = np.array(savings)
    wins = int((savings > 0).sum())

    print(f"mean saving:    {savings.mean():.2f}%")
    print(f"median saving:  {np.median(savings):.2f}%")
    print(f"std dev:        {savings.std(ddof=1):.2f}%")
    print(f"min / max:      {savings.min():.2f}% / {savings.max():.2f}%")
    print(f"5th / 95th pct: {np.percentile(savings, 5):.2f}% / {np.percentile(savings, 95):.2f}%")
    print(f"days smart wins: {wins}/{len(savings)}")
    print(f"aggregate: naive={naive_total:.0f}c smart={smart_total:.0f}c "
          f"({100 * (naive_total - smart_total) / naive_total:.2f}% saved)")

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.hist(savings, bins=40, color="#27ae60", edgecolor="black", lw=0.4)
    ax.axvline(savings.mean(), color="#c0392b", lw=1.4, ls="--",
               label=f"mean = {savings.mean():.1f}%")
    ax.axvline(np.median(savings), color="#2c3e50", lw=1.4, ls=":",
               label=f"median = {np.median(savings):.1f}%")
    ax.set_xlabel("Per-day net-cost saving of Smart V1 vs naive (%)")
    ax.set_ylabel("Number of days")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    out = IMAGE_DIR / "algo_backtest_hist.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
