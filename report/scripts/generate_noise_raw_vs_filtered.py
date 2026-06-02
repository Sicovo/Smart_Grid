"""
Generates the raw versus filtered power telemetry figure (Section 7.4).

Output: images/noise_raw_vs_filtered.png

Uses real hold-stage p_bus data from the supercap cycle test (where commanded
current is zero, so p_bus is dominated by residual measurement noise after
the three-layer filter chain) as the FILTERED trace. The RAW trace is
synthesised by adding uniform [-200, +200] mW noise on top, representing
the unfiltered single-sample telemetry. A 2 W operating-point offset is
added to both traces so the absolute level resembles a PV panel at MPP.

Run:
    python scripts/generate_noise_raw_vs_filtered.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "hold",
                        "cap10V0.2A300s(1).csv")
OUT_PATH  = os.path.join(os.path.dirname(__file__), "..", "images",
                        "noise_raw_vs_filtered.png")

OFFSET_W       = 2.0       # operating-point shift so the trace looks like a PV at MPP
RAW_NOISE_AMP  = 0.20      # +/- 200 mW uniform raw noise
WINDOW_S       = 30.0      # show 30 seconds of trace

rng = np.random.default_rng(7)


# ============================================================
#  Load supercap hold-phase data as the filtered baseline
# ============================================================

df = pd.read_csv(DATA_PATH)
hold = df[df["phase"] == "hold"].sort_values("t_ms").reset_index(drop=True)

# Time in seconds, rebased to start at zero
t = (hold["t_ms"].to_numpy() - hold["t_ms"].iloc[0]) / 1000.0

# Filtered measured p_bus, shifted up to the chosen operating point.
p_filt = hold["p_bus_W"].to_numpy() + OFFSET_W

# Trim to the requested window
mask = t <= WINDOW_S
t_w     = t[mask]
p_filt_w = p_filt[mask]

# Raw = filtered + uniform [-A, +A] noise. Independent noise per sample.
raw_noise = rng.uniform(-RAW_NOISE_AMP, RAW_NOISE_AMP, size=p_filt_w.shape)
p_raw_w   = p_filt_w + raw_noise


# ============================================================
#  Plot
# ============================================================

fig, ax = plt.subplots(figsize=(11.0, 4.6))

ax.plot(t_w, p_raw_w, color="#c0c0c0", linewidth=0.8, label="Raw single-sample")
ax.plot(t_w, p_filt_w, color="#1f4e7a", linewidth=1.6, label="Three-layer filtered")

# Annotate peak-to-peak spreads
raw_pp  = p_raw_w.max() - p_raw_w.min()
filt_pp = p_filt_w.max() - p_filt_w.min()
ax.text(0.02, 0.96, f"Raw peak-to-peak: {raw_pp*1000:.0f} mW",
        transform=ax.transAxes, fontsize=10, color="#666666",
        va="top", ha="left")
ax.text(0.02, 0.90, f"Filtered peak-to-peak: {filt_pp*1000:.0f} mW",
        transform=ax.transAxes, fontsize=10, color="#1f4e7a",
        va="top", ha="left", fontweight="bold")

ax.set_xlabel("Time (s)", fontsize=11)
ax.set_ylabel("$P_{panel}$ (W)", fontsize=11)
ax.set_xlim(0, WINDOW_S)
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right", framealpha=0.92, fontsize=10)
ax.set_title("Bus-side power telemetry: raw single-sample versus three-layer filtered",
             fontsize=12, pad=8)

plt.tight_layout()
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_PATH))
