"""
Representative supercapacitor cycle trace (Section 4.3).

Reads the measured cycle-test logs in report/data/ (one CSV per run, named
cap<bus>V<current>A(<run>).csv) and renders the representative 10 V / 0.2 A
charge-and-discharge cycle as:

  images/supercap_cycle_trace.png

The efficiency sweeps (current, bus voltage, hold duration) are produced by
generate_supercap_hold_analysis.py from the extended dataset under
report/data/hold/.

Run:
    python scripts/generate_supercap_results.py
"""

import os
import re
import csv
import glob
import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
IMG  = os.path.join(HERE, "..", "images")

NAME_RE = re.compile(r"cap([\d.]+)V([\d.]+)A\((\d)\)")


def load():
    runs = []
    for path in sorted(glob.glob(os.path.join(DATA, "cap*.csv"))):
        m = NAME_RE.search(os.path.basename(path))
        if not m:
            continue
        bus, cur, run = float(m.group(1)), float(m.group(2)), int(m.group(3))
        with open(path, newline="") as f:
            rows = [r for r in csv.DictReader(f)]

        def col(key):
            return np.array([float(r[key]) for r in rows])

        E_in  = col("E_in_J").max()
        E_out = col("E_out_J").max()
        runs.append({
            "bus": bus, "cur": cur, "run": run,
            "E_in": E_in, "E_out": E_out, "eta": E_out / E_in,
            "rows": rows,
        })
    return runs


runs = load()


# ============================================================
#  Representative cycle trace (10 V bus, 0.2 A, run 1)
# ============================================================

trace = next(r for r in runs if r["bus"] == 10.0 and r["cur"] == 0.2 and r["run"] == 1)
rows = sorted(trace["rows"], key=lambda r: int(r["t_ms"]))
t   = np.array([int(r["t_ms"]) for r in rows]) / 1000.0
vc  = np.array([float(r["v_cap"]) for r in rows])
ein = np.array([float(r["E_in_J"]) for r in rows])
eout = np.array([float(r["E_out_J"]) for r in rows])
ph  = [r["phase"] for r in rows]


def span(phase):
    ts = [t[i] for i, p in enumerate(ph) if p == phase]
    return (min(ts), max(ts)) if ts else None


fig, ax = plt.subplots(figsize=(10.0, 5.0))
for phase, color, label in [("charging", "#cfe0f3", "charge"),
                            ("discharging", "#f3d2cf", "discharge")]:
    s = span(phase)
    if s:
        ax.axvspan(s[0], s[1], color=color, alpha=0.7, zorder=0, label=label)

ax.plot(t, vc, color="#1f77b4", linewidth=2.0, label="$V_{cap}$")
ax.set_xlabel("Time (s)", fontsize=12)
ax.set_ylabel("Capacitor voltage  $V_{cap}$  (V)", color="#1f77b4", fontsize=12)
ax.tick_params(axis="y", labelcolor="#1f77b4")
ax.set_ylim(10, 16.5)
ax.grid(True, alpha=0.3)

ax2 = ax.twinx()
ax2.plot(t, ein,  color="#2ca02c", linewidth=1.8, label="$E_{in}$ (bus)")
ax2.plot(t, eout, color="#d62728", linewidth=1.8, label="$E_{out}$ (bus)")
ax2.set_ylabel("Energy  (J)", fontsize=12)
ax2.set_ylim(0, 45)

h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="center right", fontsize=9, framealpha=0.95)
ax.set_title(f"Supercapacitor cycle test (10 V bus, 0.2 A), "
             f"$E_{{in}}$ = {trace['E_in']:.1f} J, $E_{{out}}$ = {trace['E_out']:.1f} J, "
             f"$\\eta_{{RT}}$ = {100*trace['eta']:.0f}%", fontsize=12)

plt.tight_layout()
os.makedirs(IMG, exist_ok=True)
out = os.path.join(IMG, "supercap_cycle_trace.png")
plt.savefig(out, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(out))
plt.close(fig)
