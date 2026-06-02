"""
Measured Import SMPS conversion efficiency versus bus voltage at three load
currents (Section 5.3).

Sweep: V_PSU fixed at 12 V; the bus voltage V_bus is commanded across nine
points from 7 V to ~11 V (deliberately wider than the 9.9 V to 10.1 V
dead-band so the duty-cycle dependency is captured across the full
operating range); inductor current is held by the outer voltage PI at 0.1,
0.2 and 0.3 A. Efficiency = P_bus / P_PSU, with P_PSU read from the bench
PSU's built-in current readout and P_bus from the firmware telemetry.

The buck duty D = V_bus / V_PSU walks from about 0.58 (at 7 V) to 0.92 (at
11 V) across the sweep. Efficiency rises with both bus voltage (lower
switching loss as the duty approaches unity) and load current (fixed gate-
drive and switching overhead amortised over more delivered power).

Saves to:  images/import_efficiency.png
"""

import os
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
IMG  = os.path.join(HERE, "..", "images")

# (V_bus, D, eta) at each commanded inductor current.
DATA = {
    "0.1 A": [
        ( 7.00, 0.58, 0.7778), ( 7.49, 0.62, 0.7901), ( 8.08, 0.67, 0.8112),
        ( 8.53, 0.71, 0.8170), ( 8.96, 0.75, 0.8205), ( 9.55, 0.80, 0.8290),
        (10.06, 0.84, 0.8383), (10.51, 0.88, 0.8421), (10.98, 0.92, 0.8472),
    ],
    "0.2 A": [
        ( 7.04, 0.59, 0.8691), ( 7.49, 0.62, 0.8730), ( 8.09, 0.67, 0.8813),
        ( 8.49, 0.71, 0.8844), ( 9.01, 0.75, 0.8886), ( 9.52, 0.79, 0.8964),
        ( 9.98, 0.83, 0.8991), (10.49, 0.87, 0.9059), (11.07, 0.92, 0.9134),
    ],
    "0.3 A": [
        ( 7.00, 0.58, 0.8929), ( 7.49, 0.62, 0.9002), ( 8.03, 0.67, 0.9043),
        ( 8.50, 0.71, 0.9081), ( 9.01, 0.75, 0.9119), ( 9.50, 0.79, 0.9170),
        (10.03, 0.84, 0.9253), (10.49, 0.87, 0.9267), (11.08, 0.92, 0.9358),
    ],
}

LABELS  = ["0.1 A", "0.2 A", "0.3 A"]
COLORS  = {"0.1 A": "#b4cbe4", "0.2 A": "#3d6da5", "0.3 A": "#1a3e7a"}
MARKERS = {"0.1 A": "s", "0.2 A": "^", "0.3 A": "o"}

fig, ax = plt.subplots(figsize=(9.0, 5.0))

for label in LABELS:
    pts = DATA[label]
    vb  = np.array([p[0] for p in pts])
    eta = np.array([100 * p[2] for p in pts])
    ax.plot(vb, eta, "-" + MARKERS[label], color=COLORS[label], markersize=7,
            linewidth=1.6, markerfacecolor=COLORS[label],
            markeredgecolor="white", markeredgewidth=0.8,
            label=f"$I_L$ = {label}")

# nominal bus
ax.axvline(10.0, color="#888888", linewidth=0.9, linestyle=":", alpha=0.7, zorder=1)
ax.text(10.05, 77, r"nominal $V_{\mathrm{bus}} = 10$ V",
        fontsize=9, color="#666666", va="bottom")

ax.set_xlim(6.6, 11.5)
ax.set_ylim(76, 96)
ax.set_xlabel(r"Bus voltage  $V_{\mathrm{bus}}$  (V)", fontsize=11)
ax.set_ylabel(r"Conversion efficiency  $\eta_{\mathrm{import}}$  (%)", fontsize=11)
ax.set_title(r"Measured Import SMPS efficiency vs bus voltage "
             r"($V_{\mathrm{PSU}} = 12$ V)",
             fontsize=11.5)
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=10, framealpha=0.95)

plt.tight_layout()
os.makedirs(IMG, exist_ok=True)
out = os.path.join(IMG, "import_efficiency.png")
plt.savefig(out, dpi=180, bbox_inches="tight")
plt.close(fig)

# console summary
for label in LABELS:
    eta = np.array([100 * p[2] for p in DATA[label]])
    print(f"I_L = {label}: mean {eta.mean():.2f}%, std {eta.std(ddof=1):.2f}%, "
          f"range {eta.min():.1f}-{eta.max():.1f}%")
print("Saved", os.path.normpath(out))
