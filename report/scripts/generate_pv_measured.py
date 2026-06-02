"""
Generates the MEASURED PV characterisation figures (Section 3).

Outputs:
  images/pv_iv_measured.png        - measured I-V and P-V curves, 6 irradiance levels
  images/pv_vmpp_irradiance.png    - measured Vmpp and Pmax vs irradiance (the firmware lookup table)

Data is the group's own bench sweep of the panel under the solar emulator at
six dimmer settings (25% to 100%). Each sweep steps the panel voltage from
~2 V toward the open-circuit knee (with denser sampling around the MPP) and
records current and resulting power. The maximum-power voltages match the
VMPP_TABLE used by firmware/pv_smps/main.py.

Run:
    python scripts/generate_pv_measured.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt

OUT_IV   = os.path.join(os.path.dirname(__file__), "..", "images", "pv_iv_measured.png")
OUT_VMPP = os.path.join(os.path.dirname(__file__), "..", "images", "pv_vmpp_irradiance.png")

# ============================================================
#  Measured sweeps: irradiance fraction -> list of (V, I, P)
# ============================================================

# fmt: off
SWEEPS = {
    1.00: [(2.0,0.840,1.6800),(2.5,0.8333,2.0833),(3.0,0.830,2.490),(3.5,0.826,2.891),
           (4.0,0.820,3.280),(4.5,0.816,3.672),(5.0,0.810,4.050),(5.1,0.808,4.1208),
           (5.2,0.804,4.1808),(5.3,0.780,4.134),(5.4,0.763,4.1202),(5.5,0.710,3.9050),
           (5.6,0.670,3.7520),(5.7,0.630,3.5910),(5.8,0.603,3.4974),(6.0,0.551,3.306),
           (6.2,0.496,3.0752),(6.4,0.435,2.784),(6.6,0.369,2.4354),(6.8,0.298,2.0264),
           (7.0,0.224,1.568),(7.2,0.142,1.0224),(7.4,0.067,0.4958)],
    0.80: [(2.0,0.707,1.4140),(2.4,0.678,1.6272),(2.9,0.672,1.9488),(3.4,0.670,2.2780),
           (3.9,0.668,2.6052),(4.4,0.660,2.9040),(4.9,0.630,3.0870),(5.0,0.626,3.1300),
           (5.1,0.620,3.1620),(5.2,0.611,3.1772),(5.3,0.599,3.1747),(5.4,0.585,3.1590),
           (5.5,0.570,3.1350),(5.6,0.530,2.9680),(5.7,0.510,2.9070),(5.9,0.448,2.6432),
           (6.1,0.394,2.4034),(6.3,0.341,2.1483),(6.5,0.283,1.8395),(6.7,0.217,1.4539),
           (6.9,0.148,1.0212),(7.1,0.076,0.5396),(7.3,0.024,0.1752)],
    0.65: [(2.0,0.610,1.2200),(2.4,0.590,1.4160),(2.9,0.582,1.6878),(3.4,0.577,1.9618),
           (3.9,0.560,2.1840),(4.4,0.550,2.4200),(4.9,0.530,2.5970),(5.0,0.523,2.6150),
           (5.1,0.514,2.6214),(5.2,0.505,2.6260),(5.3,0.493,2.6129),(5.4,0.480,2.5920),
           (5.5,0.460,2.5300),(5.6,0.452,2.5312),(5.7,0.430,2.4510),(5.9,0.411,2.4249),
           (6.1,0.364,2.2204),(6.3,0.318,2.0034),(6.5,0.267,1.7355),(6.7,0.209,1.4003),
           (6.9,0.146,1.0074),(7.1,0.078,0.5538),(7.3,0.026,0.1898)],
    0.50: [(2.0,0.465,0.9300),(2.3,0.466,1.0718),(2.7,0.466,1.2582),(3.2,0.465,1.4880),
           (3.7,0.463,1.7131),(4.2,0.460,1.9320),(4.7,0.460,2.1620),(4.8,0.448,2.1504),
           (4.9,0.442,2.1658),(5.0,0.435,2.1750),(5.1,0.427,2.1777),(5.2,0.413,2.1476),
           (5.3,0.400,2.1200),(5.4,0.390,2.1060),(5.5,0.373,2.0515),(5.7,0.355,2.0235),
           (5.9,0.328,1.9352),(6.1,0.295,1.7995),(6.3,0.256,1.6128),(6.5,0.210,1.3650),
           (6.7,0.158,1.0586),(6.9,0.100,0.6900),(7.1,0.044,0.3124)],
    0.35: [(2.0,0.370,0.7400),(2.3,0.375,0.8625),(2.7,0.370,0.9990),(3.2,0.370,1.1840),
           (3.7,0.368,1.3616),(4.2,0.370,1.5540),(4.7,0.366,1.7202),(4.8,0.366,1.7568),
           (4.9,0.365,1.7885),(5.0,0.363,1.8150),(5.1,0.362,1.8462),(5.2,0.355,1.8460),
           (5.3,0.348,1.8444),(5.4,0.340,1.8360),(5.5,0.330,1.8150),(5.7,0.300,1.7100),
           (5.9,0.271,1.5989),(6.1,0.246,1.5006),(6.3,0.215,1.3545),(6.5,0.177,1.1505),
           (6.7,0.132,0.8844),(6.9,0.080,0.5520),(7.1,0.032,0.2272)],
    0.25: [(1.8,0.228,0.4104),(2.2,0.228,0.5016),(2.7,0.232,0.6264),(3.2,0.229,0.7328),
           (3.7,0.230,0.8510),(4.2,0.230,0.9660),(4.7,0.229,1.0763),(4.8,0.228,1.0944),
           (4.9,0.227,1.1123),(5.0,0.226,1.1300),(5.1,0.225,1.1475),(5.2,0.220,1.1440),
           (5.3,0.215,1.1395),(5.4,0.210,1.1340),(5.5,0.203,1.1165),(5.7,0.190,1.0830),
           (5.9,0.166,0.9794),(6.1,0.154,0.9394),(6.3,0.133,0.8379),(6.5,0.106,0.6890),
           (6.7,0.073,0.4891),(6.9,0.035,0.2415),(7.1,0.007,0.0497)],
}
# fmt: on

# Pinned MPP (Vmpp, Impp) — taken at the power peak of each sweep.
# These six values are the entries loaded into the firmware VMPP_TABLE.
MPP = {
    1.00: (5.2, 0.804),   # Pmax = 4.181 W
    0.80: (5.2, 0.611),   # Pmax = 3.177 W
    0.65: (5.2, 0.505),   # Pmax = 2.626 W
    0.50: (5.1, 0.427),   # Pmax = 2.178 W
    0.35: (5.1, 0.362),   # Pmax = 1.846 W
    0.25: (5.1, 0.225),   # Pmax = 1.148 W
}

LEVELS = sorted(SWEEPS.keys())                      # ascending irradiance
CMAP   = plt.cm.viridis(np.linspace(0.1, 0.9, len(LEVELS)))


# ============================================================
#  Figure 1: measured I-V and P-V curves
# ============================================================

fig, (axiv, axpv) = plt.subplots(1, 2, figsize=(11.0, 4.7))

vmpp_pts, pmax_pts, imp_pts = {}, {}, {}

for col, irr in zip(CMAP, LEVELS):
    arr = np.array(SWEEPS[irr])
    V, I, P = arr[:, 0], arr[:, 1], arr[:, 2]
    label = f"{int(irr*100)}%"

    axiv.plot(V, I, "-o", color=col, markersize=2.6, linewidth=1.6, label=label)
    axpv.plot(V, P, "-o", color=col, markersize=2.6, linewidth=1.6, label=label)

    vmpp, impp = MPP[irr]
    vmpp_pts[irr], imp_pts[irr], pmax_pts[irr] = vmpp, impp, impp * vmpp
    axiv.plot(vmpp, impp, "*", color=col, markersize=11,
              markeredgecolor="k", markeredgewidth=0.4)
    axpv.plot(vmpp, impp * vmpp, "*", color=col, markersize=11,
              markeredgecolor="k", markeredgewidth=0.4)

# trace the MPP locus on the P-V panel
vlist = [vmpp_pts[i] for i in LEVELS]
plist = [pmax_pts[i] for i in LEVELS]
axpv.plot(vlist, plist, "--", color="#444444", linewidth=1.0, label="MPP locus")

axiv.set_xlabel("Panel voltage  $V_{pv}$  (V)", fontsize=11)
axiv.set_ylabel("Panel current  $I_{pv}$  (A)", fontsize=11)
axiv.set_title("Measured I-V characteristic", fontsize=12)
axiv.grid(True, alpha=0.3)
axiv.set_xlim(1.7, 8.0)
axiv.set_ylim(0, 0.92)
axiv.legend(title="Irradiance", loc="upper right", fontsize=8, ncol=2)

axpv.set_xlabel("Panel voltage  $V_{pv}$  (V)", fontsize=11)
axpv.set_ylabel("Panel power  $P_{pv}$  (W)", fontsize=11)
axpv.set_title("Measured P-V characteristic and MPP locus", fontsize=12)
axpv.grid(True, alpha=0.3)
axpv.set_xlim(1.7, 8.0)
axpv.set_ylim(0, 4.6)
axpv.legend(loc="upper left", fontsize=8, ncol=2)

fig.suptitle("PV panel characterisation under the solar emulator (measured)", fontsize=13)
plt.tight_layout(rect=[0, 0, 1, 0.95])
os.makedirs(os.path.dirname(OUT_IV), exist_ok=True)
plt.savefig(OUT_IV, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_IV))
plt.close(fig)


# ============================================================
#  Figure 2: Vmpp and Pmax vs irradiance (the firmware lookup table)
# ============================================================

irr_pct = np.array([i * 100 for i in LEVELS])
vmpp    = np.array([vmpp_pts[i] for i in LEVELS])
pmax    = np.array([pmax_pts[i] for i in LEVELS])

fig2, ax = plt.subplots(figsize=(8.4, 5.0))

l1 = ax.plot(irr_pct, vmpp, "-o", color="#1f77b4", linewidth=2.0, markersize=6,
             label="$V_{mpp}$ (lookup table)")
ax.set_xlabel("Irradiance (% of full emulator output)", fontsize=12)
ax.set_ylabel("Maximum-power voltage  $V_{mpp}$  (V)", color="#1f77b4", fontsize=12)
ax.tick_params(axis="y", labelcolor="#1f77b4")
ax.set_ylim(5.00, 5.30)
ax.grid(True, alpha=0.3)

for x, y in zip(irr_pct, vmpp):
    ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 8),
                ha="center", fontsize=8, color="#1f77b4")

ax2 = ax.twinx()
l2 = ax2.plot(irr_pct, pmax, "-s", color="#d62728", linewidth=2.0, markersize=6,
              label="$P_{max}$")
ax2.set_ylabel("Maximum power  $P_{max}$  (W)", color="#d62728", fontsize=12)
ax2.tick_params(axis="y", labelcolor="#d62728")
ax2.set_ylim(0, 4.5)

lines = l1 + l2
ax.legend(lines, [ln.get_label() for ln in lines], loc="center right", fontsize=10)
ax.set_title("Measured $V_{mpp}$ and $P_{max}$ vs irradiance", fontsize=13)

plt.tight_layout()
plt.savefig(OUT_VMPP, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_VMPP))

# Console summary
print("\nirr%   Vmpp   Imp    Pmax")
for i in LEVELS:
    print(f"{int(i*100):4d}  {vmpp_pts[i]:5.2f}  {imp_pts[i]:5.3f}  {pmax_pts[i]:5.3f}")
