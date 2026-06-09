"""Generate per-tick algorithm timing diagrams for Section 9.

Reads naive_decisions.csv from a lab run, pulls the per-tick
recommendation_json diagnostics, and plots a 4-panel stack:

  panel 1: Azure sell_price / buy_price (decision context)
  panel 2: PV bus-side power and effective load (demand + deferrables)
  panel 3: supercap commanded bus-side power (signed)
  panel 4: residual surplus (passive export) and deficit (passive import)

The same axes are produced for naive and smart V1 runs, so the visual
comparison shows how the cap dispatch and deferrable scheduling shift
energy across the day.

Output:
  report/images/algo_naive_trace.png
  report/images/algo_smart_trace.png
"""

import csv
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# CSV row sizes can exceed the default Python csv field limit (the
# recommendation_json column is large). Bump it up.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


REPO_ROOT   = Path(__file__).resolve().parents[2]
IMAGE_DIR   = REPO_ROOT / "report" / "images"
NAIVE_RUN   = Path(r"C:/Users/lenovo/Downloads/naivealgoV4test1fixed")
SMART_RUN   = Path(r"C:/Users/lenovo/Downloads/smartalgoV4test1fixed")


def load_decisions(run_dir: Path):
    """Return dict tick -> diagnostics dict from naive_decisions.csv."""
    path = run_dir / "naive_decisions.csv"
    out = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                tick = int(row["tick"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                rec = json.loads(row["recommendation_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            diag = rec.get("diagnostics") or {}
            if not diag:
                continue
            # If a tick appears more than once, keep the LATEST decision (apply path).
            out[tick] = diag
    return out


def load_prices(run_dir: Path):
    """Return dict tick -> (sell_price, buy_price) from grid_snapshots.csv."""
    path = run_dir / "grid_snapshots.csv"
    out = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                tick = int(row["tick"])
                sp = float(row["sell_price"])
                bp = float(row["buy_price"])
            except (KeyError, TypeError, ValueError):
                continue
            out[tick] = (sp, bp)
    return out


def assemble(run_dir: Path):
    diag = load_decisions(run_dir)
    prc  = load_prices(run_dir)
    ticks = sorted(set(diag) & set(prc))
    if not ticks:
        raise RuntimeError(f"No overlapping ticks found in {run_dir}")
    sell  = np.array([prc[t][0] for t in ticks], dtype=float)
    buy   = np.array([prc[t][1] for t in ticks], dtype=float)
    pv    = np.array([diag[t].get("pv_bus_W", 0.0) or 0.0 for t in ticks], dtype=float)
    load  = np.array([diag[t].get("effective_load_W", 0.0) or 0.0 for t in ticks], dtype=float)
    demand= np.array([diag[t].get("demand_W", 0.0) or 0.0 for t in ticks], dtype=float)
    cap   = np.array([diag[t].get("cap_p_W", 0.0) or 0.0 for t in ticks], dtype=float)
    surp  = np.array([diag[t].get("surplus_W", 0.0) or 0.0 for t in ticks], dtype=float)
    defi  = np.array([diag[t].get("deficit_W", 0.0) or 0.0 for t in ticks], dtype=float)
    return {
        "ticks": np.array(ticks),
        "sell": sell, "buy": buy,
        "pv": pv, "load": load, "demand": demand,
        "cap": cap, "surp": surp, "defi": defi,
    }


def plot_trace(data, title, out_path):
    ticks = data["ticks"]

    fig, axes = plt.subplots(
        4, 1, figsize=(7.2, 8.0), sharex=True,
        gridspec_kw=dict(height_ratios=[1.0, 1.2, 1.2, 1.2], hspace=0.18),
    )

    # Panel 1: Azure prices (continuous lines)
    ax = axes[0]
    ax.plot(ticks, data["sell"], color="#c0392b", lw=1.5, label="sell price (import)")
    ax.plot(ticks, data["buy"],  color="#2980b9", lw=1.5, label="buy price (export)")
    ax.set_ylabel("Price (¢/J)")
    ax.set_ylim(0, 150)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.grid(True, alpha=0.3)
    ax.set_title(title, fontsize=12, weight="bold", pad=8)

    # Panel 2: PV and effective load (per-tick step semantics)
    ax = axes[1]
    ax.fill_between(ticks, 0, data["load"], step="mid", color="#f39c12", alpha=0.35,
                    label="effective load (demand + deferrables)")
    ax.step(ticks, data["load"],   where="mid", color="#d35400", lw=1.5)
    ax.step(ticks, data["demand"], where="mid", color="#7f8c8d", lw=1.2, ls="--",
            label="base demand")
    ax.step(ticks, data["pv"],     where="mid", color="#27ae60", lw=1.5, label="PV bus-side")
    ax.set_ylabel("Power (W)")
    ax.set_ylim(0, 10)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=1)
    ax.grid(True, alpha=0.3)

    # Panel 3: cap power (signed, per-tick rectangles — no slope interpolation
    # so charge and discharge can never appear at the same tick).
    ax = axes[2]
    cap = data["cap"]
    ax.fill_between(ticks, 0, np.maximum(cap, 0), step="mid",
                    color="#27ae60", alpha=0.6, label="charging")
    ax.fill_between(ticks, 0, np.minimum(cap, 0), step="mid",
                    color="#c0392b", alpha=0.6, label="discharging")
    ax.axhline(0, color="black", lw=0.7)
    ax.set_ylabel("Cap power (W)")
    ax.set_ylim(-7.5, 7.5)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.grid(True, alpha=0.3)

    # Panel 4: residual surplus / deficit handled by droop
    ax = axes[3]
    ax.fill_between(ticks, 0,  data["surp"], step="mid", color="#2980b9", alpha=0.6,
                    label="export (residual surplus)")
    ax.fill_between(ticks, 0, -data["defi"], step="mid", color="#e67e22", alpha=0.6,
                    label="import (residual deficit)")
    ax.axhline(0, color="black", lw=0.7)
    ax.set_ylabel("Grid power (W)")
    ax.set_xlabel("Azure tick (1 tick = 5 s)")
    ax.set_ylim(-6, 4)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.grid(True, alpha=0.3)

    fig.align_ylabels(axes)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading naive V4 test1 ...")
    naive = assemble(NAIVE_RUN)
    plot_trace(
        naive,
        "Naive baseline: per-tick dispatch (V4 test 1)",
        IMAGE_DIR / "algo_naive_trace.png",
    )

    print("Loading smart V4 test1 ...")
    smart = assemble(SMART_RUN)
    plot_trace(
        smart,
        "Smart V1: per-tick dispatch (V4 test 1)",
        IMAGE_DIR / "algo_smart_trace.png",
    )


if __name__ == "__main__":
    main()
