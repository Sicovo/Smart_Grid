"""
Preview plots for the MPPT mode-comparison test run (Section 3.3.1).

Generates 4 candidate figures from data/mppt_test_run.tsv:

  1. mppt_test_means.png       - bar chart of headline mean power by mode/irr
  2. mppt_test_vmpp_trace.png  - full timeline of vmpp_target over the whole test
  3. mppt_test_transient_50pct.png - 2-panel zoom across the 50% mode switches
  4. mppt_test_ripple_grid.png - 2x2 grid of steady-state recording ripple

Run:
    python scripts/generate_mppt_test_plots.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data", "mppt_test_run.tsv")
IMG  = os.path.join(HERE, "..", "images")
os.makedirs(IMG, exist_ok=True)

# ============================================================
#  Load and tidy
# ============================================================

df = pd.read_csv(DATA, sep="\t")
df["t_s"] = df["t_ms"] / 1000.0

# Headline means: p_avg_last_W "freezes" the LAST completed recording-phase average
# at the first row of the NEXT phase. Pick it out per (irr, mode).
MODES = ["fixed", "lut", "po"]
IRRADIANCES = [25, 50, 75, 100]
MODE_COLORS = {"fixed": "#3d6da5", "lut": "#2ca02c", "po": "#d97a2c"}
MODE_LABELS = {"fixed": "Fixed", "lut": "LUT", "po": "P&O"}

# Reconstruct mean p per (irr, mode) by reading p_avg_last_W at the row AFTER
# that mode's recording phase ends. Easiest way: group by (irr, mode), take
# the LAST p_avg_last_W observed during the NEXT mode's run (or "done" / next
# irr's awaiting_setup).
def mean_table():
    """Return dict[irr][mode] = mean_W extracted from p_avg_last_W transitions."""
    out = {ir: {} for ir in IRRADIANCES}
    # iterate row-by-row; when (irr, mode) flips, the new row's p_avg_last_W
    # is the previous (irr, mode)'s mean.
    prev_key = None
    for _, row in df.iterrows():
        key = (int(row["irr_pct"]), str(row["test_step"]))
        if prev_key is not None and key != prev_key and prev_key[1] in MODES:
            ir, md = prev_key
            if ir in out and md not in out[ir]:
                out[ir][md] = float(row["p_avg_last_W"])
        prev_key = key
    return out


means = mean_table()
print("Headline means:")
for ir in IRRADIANCES:
    for md in MODES:
        print(f"  {ir:>3}% {md:>5}: {means[ir].get(md, float('nan')):.4f} W")


# ============================================================
#  Plot 1: headline bar chart
# ============================================================

def plot_means():
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(IRRADIANCES))
    width = 0.26
    for i, md in enumerate(MODES):
        vals = [means[ir].get(md, np.nan) for ir in IRRADIANCES]
        bars = ax.bar(x + (i - 1) * width, vals, width,
                      color=MODE_COLORS[md], label=MODE_LABELS[md],
                      edgecolor="white", linewidth=0.8)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.04,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=8.5, color="#222")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{ir}%" for ir in IRRADIANCES])
    ax.set_xlabel("Irradiance setting", fontsize=11)
    ax.set_ylabel("3-second-averaged panel power (W)", fontsize=11)
    ax.set_title("MPPT mode comparison: mean delivered power",
                 fontsize=12, pad=10)
    ax.legend(loc="upper left", framealpha=0.95, fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylim(0, max(max(means[ir].values()) for ir in IRRADIANCES) * 1.15)

    plt.tight_layout()
    out = os.path.join(IMG, "mppt_test_means.png")
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out)


# ============================================================
#  Plot 2: full timeline of vmpp_target
# ============================================================

def plot_vmpp_trace():
    fig, ax = plt.subplots(figsize=(13, 4.6))

    # For each (irr, mode), plot vmpp_target over time with its mode colour
    for md in MODES:
        sub = df[df["test_step"] == md]
        ax.plot(sub["t_s"], sub["vmpp_target_V"], "-",
                color=MODE_COLORS[md], linewidth=1.6,
                label=MODE_LABELS[md])

    # Mark irradiance-phase boundaries (where awaiting_setup with new irr begins)
    prev_irr = None
    for _, row in df.iterrows():
        if row["phase"] == "awaiting_setup" and row["irr_pct"] != prev_irr:
            ax.axvline(row["t_s"], color="#888", linestyle=":",
                       linewidth=0.8, alpha=0.6)
            ax.text(row["t_s"] + 1, 5.45, f"{int(row['irr_pct'])}%",
                    fontsize=10, color="#555", va="top", ha="left")
            prev_irr = row["irr_pct"]

    # P&O clamp lines
    ax.axhline(4.75, color="#c0392b", linestyle="--", linewidth=0.9,
               alpha=0.5)
    ax.axhline(5.50, color="#c0392b", linestyle="--", linewidth=0.9,
               alpha=0.5)
    ax.text(0.5, 4.78, "P&O lower clamp 4.75 V",
            fontsize=8, color="#c0392b", va="bottom")
    ax.text(0.5, 5.47, "P&O upper clamp 5.50 V",
            fontsize=8, color="#c0392b", va="top")

    ax.set_xlabel("Time (s)", fontsize=11)
    ax.set_ylabel("vmpp_target (V)", fontsize=11)
    ax.set_title("MPPT vmpp_target across the full mode-comparison test",
                 fontsize=12, pad=10)
    ax.set_xlim(0, df["t_s"].max() + 2)
    ax.set_ylim(4.7, 5.55)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", framealpha=0.95, fontsize=10, ncol=3)

    plt.tight_layout()
    out = os.path.join(IMG, "mppt_test_vmpp_trace.png")
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out)


# ============================================================
#  Plot 3: 50% irradiance, 2-panel transient zoom across all 3 modes
# ============================================================

def plot_transient_50pct():
    # 50% irradiance spans roughly t=52 to t=82
    sub = df[(df["irr_pct"] == 50) &
             (df["phase"].isin(["settling", "recording"]))].copy()

    fig, (ax_v, ax_p) = plt.subplots(2, 1, figsize=(12, 6),
                                     sharex=True,
                                     gridspec_kw={"hspace": 0.08})

    for md in MODES:
        seg = sub[sub["test_step"] == md]
        ax_v.plot(seg["t_s"], seg["vmpp_target_V"], "-",
                  color=MODE_COLORS[md], linewidth=1.8,
                  label=MODE_LABELS[md])
        ax_v.plot(seg["t_s"], seg["v_panel_V"], ":",
                  color=MODE_COLORS[md], linewidth=1.0, alpha=0.7)
        ax_p.plot(seg["t_s"], seg["p_panel_W"], "-",
                  color=MODE_COLORS[md], linewidth=1.4,
                  label=MODE_LABELS[md])

    # Mode-switch boundaries: where test_step value changes
    prev_md = None
    for _, row in sub.iterrows():
        md = row["test_step"]
        if prev_md is not None and md != prev_md:
            ax_v.axvline(row["t_s"], color="#666", linestyle="--",
                         linewidth=0.8, alpha=0.5)
            ax_p.axvline(row["t_s"], color="#666", linestyle="--",
                         linewidth=0.8, alpha=0.5)
        prev_md = md

    ax_v.set_ylabel("Voltage (V)", fontsize=11)
    ax_v.set_title(
        "50% irradiance: mode-switch transient response (solid = vmpp_target, dotted = v_panel)",
        fontsize=12, pad=8)
    ax_v.grid(True, alpha=0.3)
    ax_v.legend(loc="upper right", framealpha=0.95, fontsize=10, ncol=3)

    ax_p.set_xlabel("Time (s)", fontsize=11)
    ax_p.set_ylabel("Panel power (W)", fontsize=11)
    ax_p.grid(True, alpha=0.3)
    ax_p.set_ylim(1.85, 2.00)

    plt.tight_layout()
    out = os.path.join(IMG, "mppt_test_transient_50pct.png")
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out)


# ============================================================
#  Plot 4: 2x2 grid of steady-state recording-phase ripple
# ============================================================

def plot_ripple_grid():
    fig, axes = plt.subplots(2, 2, figsize=(12, 7),
                             gridspec_kw={"hspace": 0.32, "wspace": 0.22})
    axes = axes.flatten()

    for ax, ir in zip(axes, IRRADIANCES):
        rec = df[(df["irr_pct"] == ir) & (df["phase"] == "recording")]

        for md in MODES:
            seg = rec[rec["test_step"] == md]
            if len(seg) == 0:
                continue
            # Normalise time so each mode's segment starts at t=0
            t0 = seg["t_s"].iloc[0]
            ax.plot(seg["t_s"] - t0, seg["p_panel_W"],
                    "-", color=MODE_COLORS[md], linewidth=1.2,
                    label=MODE_LABELS[md])

        ax.set_title(f"{ir}% irradiance — recording phase", fontsize=11)
        ax.set_xlabel("Time within recording window (s)", fontsize=10)
        ax.set_ylabel("p_panel (W)", fontsize=10)
        ax.grid(True, alpha=0.3)
        if ir == 25:
            ax.legend(loc="lower right", fontsize=9, framealpha=0.95)

    plt.suptitle("Per-mode steady-state ripple at each irradiance",
                 fontsize=13, y=1.00)
    plt.tight_layout()
    out = os.path.join(IMG, "mppt_test_ripple_grid.png")
    plt.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("Saved", out)


if __name__ == "__main__":
    plot_means()
    plot_vmpp_trace()
    plot_transient_50pct()
    plot_ripple_grid()
