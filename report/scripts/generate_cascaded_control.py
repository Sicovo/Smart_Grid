"""
Generates the cascaded control block diagram for Import / Export SMPS
(Section 5.1.2).

Output: images/cascaded_control_block.png

Outer V PI -> I_ref -> Inner I PI -> Duty -> SMPS plant -> V_bus, I_L.
Sign-flipped summing junction differentiates Import (V_target - V_bus) from
Export (V_bus - V_target).

Run:
    python scripts/generate_cascaded_control.py
"""

import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "images",
                        "cascaded_control_block.png")

EDGE     = "#1f4e7a"
BOX_FILL = "#e8f1f9"
PLANT_F  = "#fff4e6"
ARROW_C  = "#333333"
SIGN_C   = "#c0392b"


def block(ax, x, y, w, h, label, sub=None, fill=BOX_FILL):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                linewidth=1.5, edgecolor=EDGE, facecolor=fill))
    ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), label,
            ha="center", va="center", fontsize=11, fontweight="bold",
            color="#0d2840")
    if sub:
        ax.text(x + w / 2, y + h * 0.25, sub, ha="center", va="center",
                fontsize=8.6, style="italic", color="#555")


def summer(ax, x, y, r=0.22):
    ax.add_patch(Circle((x, y), r, facecolor="white", edgecolor=EDGE,
                        linewidth=1.4))
    ax.plot([x - r * 0.55, x + r * 0.55], [y, y], color=EDGE, linewidth=1.2)
    ax.plot([x, x], [y - r * 0.55, y + r * 0.55], color=EDGE, linewidth=1.2)


def arrow(ax, x1, y1, x2, y2, label=None, label_off=(0.0, 0.18),
          rad=0.0, color=ARROW_C):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 arrowstyle="-|>", color=color, linewidth=1.6,
                                 mutation_scale=14,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + label_off[0], my + label_off[1], label,
                ha="center", va="bottom", fontsize=9.2,
                color=color, style="italic")


fig, ax = plt.subplots(figsize=(13, 4.4))
ax.set_xlim(0, 13)
ax.set_ylim(0, 4.6)
ax.axis("off")

y_main = 2.6
h_box  = 1.0

# V_target input
ax.text(0.45, y_main, "V_target", ha="right", va="center",
        fontsize=10.5, fontweight="bold", color="#0d2840")

# Outer summer
sum1_x = 1.1
summer(ax, sum1_x, y_main)
arrow(ax, 0.5, y_main, sum1_x - 0.25, y_main, label=None)
ax.text(sum1_x + 0.05, y_main + 0.32, "+", fontsize=11, fontweight="bold",
        color=SIGN_C)
ax.text(sum1_x - 0.35, y_main - 0.05, "-", fontsize=12, fontweight="bold",
        color=SIGN_C)

# Outer V PI block
block(ax, 1.85, y_main - h_box / 2, 2.4, h_box, "Outer V PI",
      "voltage error -> I_ref")
arrow(ax, sum1_x + 0.25, y_main, 1.85, y_main)

# I_ref signal
arrow(ax, 4.25, y_main, 5.05, y_main, label="I_ref", label_off=(0, 0.18))

# Inner summer
sum2_x = 5.3
summer(ax, sum2_x, y_main)
ax.text(sum2_x + 0.05, y_main + 0.32, "+", fontsize=11, fontweight="bold",
        color=SIGN_C)
ax.text(sum2_x - 0.35, y_main - 0.05, "-", fontsize=12, fontweight="bold",
        color=SIGN_C)

# Inner I PI block
block(ax, 6.0, y_main - h_box / 2, 2.4, h_box, "Inner I PI",
      "current error -> duty")
arrow(ax, sum2_x + 0.25, y_main, 6.0, y_main)

# Duty signal
arrow(ax, 8.4, y_main, 9.2, y_main, label="Duty", label_off=(0, 0.18))

# SMPS plant block
block(ax, 9.45, y_main - h_box / 2, 2.4, h_box, "SMPS Plant",
      "synchronous buck", fill=PLANT_F)
arrow(ax, 8.4, y_main, 9.45, y_main)

# Output arrow
arrow(ax, 11.85, y_main, 12.7, y_main)
ax.text(12.78, y_main, "V_bus", ha="left", va="center",
        fontsize=10.5, fontweight="bold", color="#0d2840")

# Feedback paths
# V_bus feedback (long): from plant down and back to outer summer
v_fb_y = y_main - 1.55
ax.add_patch(FancyArrowPatch((10.65, y_main - h_box / 2), (10.65, v_fb_y),
                             arrowstyle="-", color=ARROW_C, linewidth=1.5))
ax.add_patch(FancyArrowPatch((10.65, v_fb_y), (sum1_x, v_fb_y),
                             arrowstyle="-", color=ARROW_C, linewidth=1.5))
ax.add_patch(FancyArrowPatch((sum1_x, v_fb_y), (sum1_x, y_main - 0.25),
                             arrowstyle="-|>", color=ARROW_C, linewidth=1.5,
                             mutation_scale=14))
ax.text((10.65 + sum1_x) / 2, v_fb_y - 0.22, "V_bus feedback",
        ha="center", va="top", fontsize=9, style="italic", color="#444")

# I_L feedback (shorter): from plant up over to inner summer
i_fb_y = y_main + 1.05
ax.add_patch(FancyArrowPatch((10.65, y_main + h_box / 2), (10.65, i_fb_y),
                             arrowstyle="-", color=ARROW_C, linewidth=1.5))
ax.add_patch(FancyArrowPatch((10.65, i_fb_y), (sum2_x, i_fb_y),
                             arrowstyle="-", color=ARROW_C, linewidth=1.5))
ax.add_patch(FancyArrowPatch((sum2_x, i_fb_y), (sum2_x, y_main + 0.25),
                             arrowstyle="-|>", color=ARROW_C, linewidth=1.5,
                             mutation_scale=14))
ax.text((10.65 + sum2_x) / 2, i_fb_y + 0.15, "I_L feedback (INA219)",
        ha="center", va="bottom", fontsize=9, style="italic", color="#444")

# Sign-flip annotation
ax.text(6.5, 0.45,
        "Import outer error = V_target - V_bus    Export outer error = V_bus - V_target    "
        "(sign of the outer error flipped between the two modules; everything else identical)",
        ha="center", va="center", fontsize=9.2,
        color=SIGN_C, style="italic")

ax.set_title("Cascaded Control: Import and Export SMPS share one structure",
             fontsize=12.5, pad=10)

plt.tight_layout()
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print("Saved", os.path.normpath(OUT_PATH))
