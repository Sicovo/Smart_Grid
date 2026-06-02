"""
Generates the 3-tier UI stack architecture diagram (Section 8.1).

Output: images/ui_stack_architecture.png

Shows the three software tiers (Pico W firmware HTTP servers, FastAPI/SQLite
backend, React frontend) with independent telemetry and command paths. The
telemetry path runs bottom-up through the backend; the command path goes
directly from browser to module HTTP server on the LEFT side of the diagram,
fully outside the backend box so the bypass is visually unambiguous.

Run:
    python scripts/generate_ui_stack.py
"""

import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "images",
                        "ui_stack_architecture.png")

# Style
BOX_FILL = "#e8f1f9"
BOX_EDGE = "#1f4e7a"
TELEM_C  = "#1f77b4"
CMD_C    = "#c0392b"
SUB_C    = "#555555"


def box(ax, x, y, w, h, label, sub=""):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                          linewidth=1.6, edgecolor=BOX_EDGE, facecolor=BOX_FILL)
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h * 0.66, label, ha="center", va="center",
            fontsize=11.5, fontweight="bold", color="#0d2840")
    if sub:
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
                fontsize=9, style="italic", color=SUB_C)


fig, ax = plt.subplots(figsize=(11.5, 6.4))
ax.set_xlim(0, 11.5)
ax.set_ylim(0, 8.2)
ax.axis("off")

# Boxes shifted right to leave a clear left-side lane for the command arrow.
LEFT_LANE = 1.3  # x-coordinate of the command-path vertical run

# Top: React frontend
box(ax, 2.6, 6.1, 7.8, 1.5, "React + Vite Frontend (browser)",
    "My Energy / SMPS Overview / SMPS Modules")

# Middle: FastAPI backend + SQLite
box(ax, 2.6, 3.4, 7.8, 1.5, "FastAPI Backend + SQLite",
    "1 Hz poller writes telemetry and grid signals to time-stamped tables")

# Bottom: per-module Pico W HTTP servers
box(ax, 2.6, 0.4, 7.8, 1.5, "Pico W Module Firmware: HTTP Servers (one per SMPS)",
    "Telemetry endpoint + command endpoint, on second core, isolated from 1 kHz control")

# Telemetry path arrows (centred between the boxes, blue)
TELEM_X = 6.5
ax.add_patch(FancyArrowPatch((TELEM_X, 1.9), (TELEM_X, 3.4), arrowstyle="-|>",
                             color=TELEM_C, linewidth=2.4, mutation_scale=22))
ax.text(TELEM_X + 0.25, 2.65, "telemetry\n(1 Hz poll)", color=TELEM_C,
        fontsize=10, va="center", ha="left")

ax.add_patch(FancyArrowPatch((TELEM_X, 4.9), (TELEM_X, 6.1), arrowstyle="-|>",
                             color=TELEM_C, linewidth=2.4, mutation_scale=22))
ax.text(TELEM_X + 0.25, 5.5, "REST read", color=TELEM_C,
        fontsize=10, va="center", ha="left")

# Command path (red): frontend left edge -> down the LEFT LANE -> module left edge.
# Three explicit segments, all OUTSIDE the FastAPI box, so the bypass is clear.
FRONT_LEFT_X  = 2.6
MODULE_LEFT_X = 2.6
FRONT_Y       = 6.5
MODULE_Y      = 1.2

# Segment 1: out from frontend left edge into the lane (down-left)
ax.add_patch(FancyArrowPatch((FRONT_LEFT_X, FRONT_Y), (LEFT_LANE, FRONT_Y),
                             arrowstyle="-", color=CMD_C, linewidth=2.4))
# Segment 2: vertical down the lane
ax.add_patch(FancyArrowPatch((LEFT_LANE, FRONT_Y), (LEFT_LANE, MODULE_Y),
                             arrowstyle="-", color=CMD_C, linewidth=2.4))
# Segment 3: back into module left edge (terminate with arrowhead)
ax.add_patch(FancyArrowPatch((LEFT_LANE, MODULE_Y), (MODULE_LEFT_X, MODULE_Y),
                             arrowstyle="-|>", color=CMD_C, linewidth=2.4,
                             mutation_scale=22))

# Command label, vertical along the lane
ax.text(LEFT_LANE - 0.18, 3.8, "commands\n(browser to module,\nbypasses backend)",
        color=CMD_C, fontsize=10, va="center", ha="right",
        rotation=90)

# Legend top-right
ax.plot([8.6, 9.2], [7.85, 7.85], color=TELEM_C, linewidth=2.6)
ax.text(9.35, 7.85, "Telemetry path", color=TELEM_C, fontsize=10,
        fontweight="bold", va="center")
ax.plot([8.6, 9.2], [7.45, 7.45], color=CMD_C, linewidth=2.6)
ax.text(9.35, 7.45, "Command path", color=CMD_C, fontsize=10,
        fontweight="bold", va="center")

ax.set_title("User Interface Stack: independent telemetry and command paths",
             fontsize=13, pad=12)

plt.tight_layout()
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_PATH))
