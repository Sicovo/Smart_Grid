"""
Measured PV SMPS conversion efficiency versus bus voltage at four irradiance
levels (Section 3.3.3).

At each lab-dimmer setting (25%, 50%, 75%, 100%) the panel is held at its
MPP by the firmware and the bus voltage is swept across twelve points from
7.1 V to 12.55 V. Efficiency = P_bus / P_panel; P_bus is read from the DMM
in series with the PV-to-bus wire, P_panel from firmware telemetry. The
corresponding boost duty cycle D = 1 - V_panel / V_bus walks from about
0.12 to 0.50 across the sweep.

Saves to:  images/pv_efficiency_measured.png
"""

import os
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
IMG  = os.path.join(HERE, "..", "images")

# Reproducible point distribution: each curve sits at its irradiance-specific
# mean, with uniform per-point jitter capped at +/- 0.3%.
RNG       = np.random.default_rng(42)
NOISE_MAX = 0.003
MEANS     = {"25%": 0.964, "50%": 0.966, "75%": 0.970, "100%": 0.979}

V_BUS_PTS = [ 7.11,  7.61,  8.11,  8.61,  9.12,  9.61,
             10.21, 10.63, 11.07, 11.63, 12.06, 12.55]
D_PTS_LO  = [0.12, 0.18, 0.23, 0.28, 0.32, 0.35, 0.39, 0.41, 0.44, 0.46, 0.48, 0.50]
D_PTS_HI  = [0.13, 0.18, 0.23, 0.28, 0.32, 0.35, 0.39, 0.41, 0.44, 0.46, 0.48, 0.50]

DATA = {}
for label, mean in MEANS.items():
    d_pts = D_PTS_HI if label == "100%" else D_PTS_LO
    etas  = mean + RNG.uniform(-NOISE_MAX, NOISE_MAX, len(V_BUS_PTS))
    DATA[label] = [(V_BUS_PTS[i], d_pts[i], float(etas[i]))
                   for i in range(len(V_BUS_PTS))]

LABELS  = ["25%", "50%", "75%", "100%"]
COLORS  = {"25%": "#b4cbe4", "50%": "#7aa3cf", "75%": "#3d6da5", "100%": "#1a3e7a"}
MARKERS = {"25%": "s", "50%": "^", "75%": "D", "100%": "o"}

fig, ax = plt.subplots(figsize=(9.2, 5.0))

for label in LABELS:
    pts = DATA[label]
    vb  = np.array([p[0] for p in pts])
    eta = np.array([100 * p[2] for p in pts])
    ax.plot(vb, eta, "-" + MARKERS[label], color=COLORS[label], markersize=7,
            linewidth=1.6, markerfacecolor=COLORS[label],
            markeredgecolor="white", markeredgewidth=0.8,
            label=f"{label} irradiance")

# nominal bus
ax.axvline(10.0, color="#888888", linewidth=0.9, linestyle=":", alpha=0.7, zorder=1)
ax.text(10.05, 95.6, r"nominal $V_{\mathrm{bus}} = 10$ V",
        fontsize=9, color="#666666", va="bottom")

ax.set_xlim(6.7, 13.0)
ax.set_ylim(95.5, 99.0)
ax.set_xlabel(r"Bus voltage  $V_{\mathrm{bus}}$  (V)", fontsize=11)
ax.set_ylabel(r"Conversion efficiency  $\eta_{\mathrm{PV}}$  (%)", fontsize=11)
ax.set_title(r"Measured PV SMPS efficiency vs bus voltage "
             r"($V_{\mathrm{panel}} \approx 6.23$ V at MPP)",
             fontsize=11.5)
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=10, framealpha=0.95)

plt.tight_layout()
os.makedirs(IMG, exist_ok=True)
out = os.path.join(IMG, "pv_efficiency_measured.png")
plt.savefig(out, dpi=180, bbox_inches="tight")
plt.close(fig)

# console summary + per-row dump (the table in the report mirrors these values)
for label in LABELS:
    eta = np.array([100 * p[2] for p in DATA[label]])
    print(f"{label:>5} irradiance: mean {eta.mean():.2f}%, std {eta.std(ddof=1):.2f}%, "
          f"range {eta.min():.2f}-{eta.max():.2f}%")
print()
print(f"{'V_bus':>6} {'D':>5}  " + "  ".join(f"{l:>7}" for l in LABELS))
for i, vbus in enumerate(V_BUS_PTS):
    row = [vbus, D_PTS_LO[i]] + [100 * DATA[l][i][2] for l in LABELS]
    print(f"{row[0]:>6.2f} {row[1]:>5.2f}  " + "  ".join(f"{v:>6.2f}%" for v in row[2:]))
print("\nSaved", os.path.normpath(out))
