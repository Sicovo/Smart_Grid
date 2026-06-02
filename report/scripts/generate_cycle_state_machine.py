"""
Generates the supercap cycle-test state machine diagram (Section 4.3.2).

Output: images/supercap_cycle_state_machine.png

Linear flow: precharge -> settle 1 -> charge -> settle 2 -> discharge ->
settle 3 -> done. State NAMES only in the boxes; per-state behaviour is
described in the report prose, not in subtitles inside cramped boxes.
A single labelled arrow from the main chain into an aborted state covers
the trip / timeout / abort transitions out of any of the seven states.

Run:
    python scripts/generate_cycle_state_machine.py
"""

import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "images",
                        "supercap_cycle_state_machine.png")

# Style
STATE_FILL    = "#e8f1f9"
SETTLE_FILL   = "#fff4e6"
DONE_FILL     = "#dfeedf"
ABORT_FILL    = "#fbe3e3"
EDGE          = "#1f4e7a"
ARROW_C       = "#333333"


def state(ax, cx, y, w, h, label, fill):
    x = cx - w / 2
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                linewidth=1.5, edgecolor=EDGE, facecolor=fill))
    ax.text(cx, y + h / 2, label, ha="center", va="center",
            fontsize=11.5, fontweight="bold", color="#0d2840")


fig, ax = plt.subplots(figsize=(13.5, 4.2))
ax.set_xlim(0, 13.5)
ax.set_ylim(0, 4.2)
ax.axis("off")

y_main = 2.55
W, H   = 1.65, 0.9

# Centres evenly spaced along the row
centres = [1.1, 2.95, 4.8, 6.65, 8.5, 10.35, 12.2]
labels  = ["precharge", "settle 1", "charge", "settle 2",
           "discharge", "settle 3", "done"]
fills   = [STATE_FILL, SETTLE_FILL, STATE_FILL, SETTLE_FILL,
           STATE_FILL, SETTLE_FILL, DONE_FILL]

for cx, lbl, fill in zip(centres, labels, fills):
    state(ax, cx, y_main, W, H, lbl, fill)

# Forward arrows between adjacent states
for i in range(len(centres) - 1):
    x1 = centres[i] + W / 2
    x2 = centres[i + 1] - W / 2
    ax.add_patch(FancyArrowPatch((x1, y_main + H / 2), (x2, y_main + H / 2),
                                 arrowstyle="-|>", color=ARROW_C,
                                 linewidth=1.7, mutation_scale=16))

# Auto-rearm dashed loop from done back to precharge, above the chain.
# Anchor at the box tops so the arc lifts cleanly above the boxes without
# colliding with the title.
ax.add_patch(FancyArrowPatch((centres[-1], y_main + H),
                             (centres[0], y_main + H),
                             arrowstyle="-|>", color="#1f77b4", linewidth=1.4,
                             mutation_scale=14, linestyle="--",
                             connectionstyle="arc3,rad=0.15"))
ax.text(sum(centres) / len(centres), y_main + H + 0.35,
        "auto-rearm on next button click",
        ha="center", va="center", fontsize=9.5, color="#1f77b4",
        style="italic")

# Aborted state, centred below the chain
ABORT_CX, ABORT_Y = 6.65, 0.45
state(ax, ABORT_CX, ABORT_Y, 4.0, 0.85, "aborted (freeze E_in, E_out)",
      ABORT_FILL)

# One representative arrow from the main row into aborted, with a clear label
ax.add_patch(FancyArrowPatch((ABORT_CX, y_main), (ABORT_CX, ABORT_Y + 0.85),
                             arrowstyle="-|>", color="#c0392b", linewidth=1.6,
                             mutation_scale=14))
ax.text(ABORT_CX + 0.15, (y_main + ABORT_Y + 0.85) / 2,
        "from any state on trip / timeout / abort",
        ha="left", va="center", fontsize=9.5, color="#c0392b",
        style="italic")

ax.set_title("Supercapacitor Cycle-Test State Machine",
             fontsize=12.5, pad=8)

plt.tight_layout()
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_PATH))
