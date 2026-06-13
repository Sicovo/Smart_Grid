"""
Generate the implemented software-stack diagram for Section 8.1.

Output: report/images/sw_stack_architecture.png

The normal operating path is backend-mediated:
  - Pico modules push telemetry to FastAPI.
  - Browser and EMS commands pass through FastAPI before reaching /cmd.
  - The standalone Azure poller stores one grid snapshot per new (day, tick)
    and notifies the EMS loop after the database commit.

Run from the repository root:
    python report/scripts/generate_ui_stack.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_PATH = (
    Path(__file__).resolve().parent.parent / "images" / "sw_stack_architecture.png"
)

NAVY = "#173b5e"
BOX_FILL = "#edf4fa"
BOX_EDGE = "#28618e"
BACKEND_FILL = "#e7f0f8"
DB_FILL = "#f7f9fc"
TELEMETRY = "#1677b8"
COMMAND = "#c43d32"
GRID_DATA = "#2e8b57"
FALLBACK = "#7a6f8f"
TEXT = "#102a43"
SUBTEXT = "#4f6272"


def rounded_box(ax, x, y, w, h, title, subtitle="", fill=BOX_FILL, zorder=1):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=1.7,
        edgecolor=BOX_EDGE,
        facecolor=fill,
        zorder=zorder,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h * 0.64,
        title,
        ha="center",
        va="center",
        fontsize=11.2,
        fontweight="bold",
        color=TEXT,
        zorder=zorder + 1,
    )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.29,
            subtitle,
            ha="center",
            va="center",
            fontsize=8.6,
            color=SUBTEXT,
            zorder=zorder + 1,
        )
    return patch


def arrow(ax, start, end, color, label="", label_xy=None, style="-|>", dashed=False):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=17,
        linewidth=2.1,
        color=color,
        linestyle="--" if dashed else "-",
        connectionstyle="arc3",
        shrinkA=0,
        shrinkB=0,
        zorder=5,
    )
    ax.add_patch(patch)
    if label:
        x, y = label_xy or ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=8.8,
            color=color,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
            zorder=6,
        )


fig, ax = plt.subplots(figsize=(12.0, 7.2))
ax.set_xlim(0, 12)
ax.set_ylim(0, 9)
ax.axis("off")

# External source and the three deployed tiers.
rounded_box(
    ax,
    0.25,
    4.1,
    2.0,
    1.15,
    "Azure Simulation",
    "/demand, /sun,\n/price, /deferables",
    fill="#edf7f0",
)
rounded_box(
    ax,
    2.75,
    7.05,
    8.8,
    1.25,
    "React + Vite Browser Application",
    "Overview and SMPS views; all normal reads and writes use FastAPI",
)

# Backend is a tier containing the actual services used by the code.
backend = FancyBboxPatch(
    (2.75, 3.2),
    8.8,
    2.75,
    boxstyle="round,pad=0.05,rounding_size=0.08",
    linewidth=1.9,
    edgecolor=BOX_EDGE,
    facecolor=BACKEND_FILL,
    zorder=1,
)
ax.add_patch(backend)
ax.text(
    7.15,
    5.66,
    "Python Backend Tier",
    ha="center",
    va="center",
    fontsize=11.5,
    fontweight="bold",
    color=TEXT,
)

rounded_box(
    ax,
    3.05,
    3.55,
    2.35,
    1.55,
    "Azure Poller",
    "1 s /demand check;\nparallel auxiliary fetch",
    fill="#f4f8fb",
    zorder=2,
)
rounded_box(
    ax,
    5.75,
    3.55,
    2.45,
    1.55,
    "SQLite",
    "grid snapshots, module telemetry,\nalgorithm decisions",
    fill=DB_FILL,
    zorder=2,
)
rounded_box(
    ax,
    8.55,
    3.55,
    2.65,
    1.55,
    "FastAPI + EMS",
    "REST API, command proxy,\ntick-triggered algorithm loop",
    fill="#f4f8fb",
    zorder=2,
)

rounded_box(
    ax,
    2.75,
    0.45,
    8.8,
    1.55,
    "Pico W Power-Module Firmware",
    "PV, grid, export, supercapacitor and LED; HTTP on core 1, 1 kHz control on core 0",
)

# Azure ingestion and internal backend data flow.
arrow(
    ax,
    (2.25, 4.68),
    (3.05, 4.68),
    GRID_DATA,
    "HTTP GET",
    label_xy=(2.65, 4.95),
)
arrow(
    ax,
    (5.40, 4.48),
    (5.75, 4.48),
    GRID_DATA,
    "deduplicated grid snapshot",
    label_xy=(5.58, 4.84),
)
arrow(
    ax,
    (5.40, 3.92),
    (5.55, 3.38),
    GRID_DATA,
    style="-",
)
arrow(
    ax,
    (5.55, 3.38),
    (9.85, 3.38),
    GRID_DATA,
    "/internal/grid-tick after commit",
    label_xy=(7.70, 3.39),
    style="-",
)
arrow(
    ax,
    (9.85, 3.38),
    (9.85, 3.55),
    GRID_DATA,
)
arrow(
    ax,
    (8.20, 4.20),
    (8.55, 4.20),
    GRID_DATA,
    "latest state",
    label_xy=(8.38, 3.96),
)
arrow(
    ax,
    (8.55, 4.72),
    (8.20, 4.72),
    GRID_DATA,
    "persist",
    label_xy=(8.38, 4.98),
)

# Browser/backend communication: reads rise; operator commands descend.
arrow(
    ax,
    (9.35, 5.95),
    (9.35, 7.05),
    TELEMETRY,
    "latest/history/status/P&L",
    label_xy=(8.00, 6.50),
)
arrow(
    ax,
    (10.35, 7.05),
    (10.35, 5.95),
    COMMAND,
    "operator commands",
    label_xy=(11.03, 6.50),
)

# Module/backend communication: pushed telemetry rises; proxied commands descend.
arrow(
    ax,
    (9.35, 2.00),
    (9.35, 3.20),
    TELEMETRY,
    "POST /modules/tlm/{role}\n1 s heartbeat + traced push",
    label_xy=(7.65, 2.58),
)
arrow(
    ax,
    (10.35, 3.20),
    (10.35, 2.00),
    COMMAND,
    "EMS/manual proxy\nPOST /cmd",
    label_xy=(11.08, 2.58),
)

# Optional bench path, deliberately separate from normal coordinated operation.
arrow(
    ax,
    (2.75, 7.38),
    (2.48, 7.38),
    FALLBACK,
    style="-",
    dashed=True,
)
arrow(
    ax,
    (2.48, 7.38),
    (2.48, 1.22),
    FALLBACK,
    style="-",
    dashed=True,
)
arrow(
    ax,
    (2.48, 1.22),
    (2.75, 1.22),
    FALLBACK,
    style="-|>",
    dashed=True,
)
ax.text(
    2.22,
    2.82,
    "optional bench fallback:\nmodule-served dashboard\nuses local /tlm and /cmd",
    ha="center",
    va="center",
    rotation=90,
    fontsize=8.2,
    color=FALLBACK,
    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
)

# Compact legend.
legend_y = 8.68
for x, color, label, dashed in (
    (3.0, TELEMETRY, "telemetry / API reads", False),
    (5.7, COMMAND, "control commands", False),
    (8.0, GRID_DATA, "grid data / storage", False),
    (10.2, FALLBACK, "bench-only path", True),
):
    ax.plot(
        [x, x + 0.45],
        [legend_y, legend_y],
        color=color,
        linewidth=2.2,
        linestyle="--" if dashed else "-",
    )
    ax.text(x + 0.55, legend_y, label, va="center", fontsize=8.5, color=color)

ax.set_title(
    "Implemented Smart-Grid Software Stack and Communication Paths",
    fontsize=13.5,
    fontweight="bold",
    color=NAVY,
    pad=12,
)

fig.tight_layout()
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved {OUT_PATH}")
