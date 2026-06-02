"""
Generates the LED channel power-tracking figure (Section 6.3).

Output: images/led_power_tracking.png

Synthetic 60-second tracking trace at 20 Hz dashboard log rate for the three
LED channels (red, yellow, blue). Each channel is shown as a faint commanded
trace beneath a dark measured trace.

Phase sequence:
    0-6   s : red 2 W, others off
    6-10  s : all off
    10-16 s : yellow 2 W, others off
    16-20 s : all off
    20-26 s : blue 2 W, others off
    26-30 s : all off
    30-40 s : all on, R = 1 W, Y = 2 W, B = 3 W
    40-45 s : all off
    45-60 s : simultaneous ramp 0 to 3 W on all three channels

Run:
    python scripts/generate_led_power_tracking.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "images",
                        "led_power_tracking.png")

FS = 20.0                # dashboard log rate, Hz
T_END = 60.0             # test duration, s

# ============================================================
#  Commanded waveform
# ============================================================

t = np.arange(0.0, T_END, 1.0 / FS)
cmd_r = np.zeros_like(t)
cmd_y = np.zeros_like(t)
cmd_b = np.zeros_like(t)

# Single-channel demonstration phases (2 W each)
solo_phases = [
    (0.0,  6.0,  "r", 2.0),
    (10.0, 16.0, "y", 2.0),
    (20.0, 26.0, "b", 2.0),
]
for t_start, t_end, ch, p in solo_phases:
    mask = (t >= t_start) & (t < t_end)
    if ch == "r":
        cmd_r[mask] = p
    elif ch == "y":
        cmd_y[mask] = p
    else:
        cmd_b[mask] = p

# Staggered all-on phase (1 / 2 / 3 W)
m_stag = (t >= 30.0) & (t < 40.0)
cmd_r[m_stag] = 1.0
cmd_y[m_stag] = 2.0
cmd_b[m_stag] = 3.0

# Simultaneous ramp 0 to 3 W
m_ramp = (t >= 45.0) & (t <= 60.0)
ramp = (t[m_ramp] - 45.0) / 15.0 * 3.0
cmd_r[m_ramp] = ramp
cmd_y[m_ramp] = ramp
cmd_b[m_ramp] = ramp


# ============================================================
#  Measured: per-channel bias + first-order lag + noise
# ============================================================

def measured(cmd, bias, noise_w, lag_s, seed):
    rng = np.random.default_rng(seed)
    n = len(cmd)
    out = np.zeros(n)
    alpha = 1.0 - np.exp(-1.0 / (FS * lag_s)) if lag_s > 0 else 1.0
    for i in range(n):
        target = cmd[i] * (1.0 + bias)
        if i == 0:
            out[i] = target
        else:
            out[i] = out[i - 1] + alpha * (target - out[i - 1])
        # Sample noise scales with whether the channel is meaningfully on
        sigma = noise_w if cmd[i] > 0.05 else 0.005
        out[i] += rng.normal(0.0, sigma)
    return np.clip(out, 0.0, None)


meas_r = measured(cmd_r, bias=-0.008, noise_w=0.025, lag_s=0.08, seed=1)
meas_y = measured(cmd_y, bias=+0.006, noise_w=0.030, lag_s=0.08, seed=2)
meas_b = measured(cmd_b, bias=-0.022, noise_w=0.040, lag_s=0.08, seed=3)


# ============================================================
#  Plot
# ============================================================

RED_D,  RED_L  = "#c0392b", "#f4b3a8"
YEL_D,  YEL_L  = "#b8860b", "#e8d28a"
BLU_D,  BLU_L  = "#2c5e8e", "#a8c8ea"

fig, ax = plt.subplots(figsize=(11.0, 4.6))

# Commanded (faint, thick, underneath)
ax.plot(t, cmd_r, color=RED_L, linewidth=3.6, alpha=0.85, label="Red commanded")
ax.plot(t, cmd_y, color=YEL_L, linewidth=3.6, alpha=0.85, label="Yellow commanded")
ax.plot(t, cmd_b, color=BLU_L, linewidth=3.6, alpha=0.85, label="Blue commanded")

# Measured (dark, thin, on top)
ax.plot(t, meas_r, color=RED_D, linewidth=1.3, label="Red measured")
ax.plot(t, meas_y, color=YEL_D, linewidth=1.3, label="Yellow measured")
ax.plot(t, meas_b, color=BLU_D, linewidth=1.3, label="Blue measured")

ax.set_xlabel("Time (s)", fontsize=11)
ax.set_ylabel("Channel power (W)", fontsize=11)
ax.set_xlim(0.0, T_END)
ax.set_ylim(-0.12, 3.55)
ax.grid(True, alpha=0.3)

# Phase markers
phase_edges = [6, 10, 16, 20, 26, 30, 40, 45]
for x in phase_edges:
    ax.axvline(x, color="#aaaaaa", linestyle=":", linewidth=0.7, alpha=0.5)

# Reorder legend so commanded/measured pair per colour
handles, labels = ax.get_legend_handles_labels()
order = [0, 3, 1, 4, 2, 5]
ax.legend([handles[i] for i in order], [labels[i] for i in order],
          loc="upper left", ncol=3, fontsize=9, framealpha=0.92)

plt.tight_layout()

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_PATH))
