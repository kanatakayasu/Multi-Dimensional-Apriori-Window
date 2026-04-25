#!/usr/bin/env python3
"""EX-1 結果（合成データ Shape A/B/C/D）をヒートマップ化する。"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FIG_OUT = SCRIPT_DIR / "figures"
PAPER_FIGS = [
    SCRIPT_DIR.parent / "paper" / "DSAA2026" / "fig",
    SCRIPT_DIR.parent / "paper" / "DSAA2026_eng" / "fig",
]
FIG_OUT.mkdir(parents=True, exist_ok=True)
for p in PAPER_FIGS:
    p.mkdir(parents=True, exist_ok=True)

# --- EX-1 データ (3-seed average, p_embed=0.25) ---
shapes = ["Shape A", "Shape B", "Shape C", "Shape D"]

# EX-1-1: F1 (Ours, Colocation, STCP-Miner)
f1_methods = ["Ours†", "Colocation", "STCP-Miner"]
f1_data = np.array([
    [1.000, 0.876, 0.917],
    [1.000, 0.825, 0.895],
    [1.000, 0.816, 0.850],
    [1.000, 0.356, 0.601],
])

# EX-1-2: mean Jaccard (Ours, LISA, MZoom, ST-DBSCAN)
mj_methods = ["Ours†", "LISA", "MZoom", "ST-DBSCAN"]
mj_data = np.array([
    [1.000, 0.150, 0.029, 0.190],
    [1.000, 0.157, 0.028, 0.188],
    [1.000, 0.145, 0.026, 0.174],
    [1.000, 0.098, 0.020, 0.190],
])

plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "cm",
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "axes.linewidth": 0.6,
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.0, 2.6),
                                 gridspec_kw={"width_ratios": [3, 4]})

# --- (a) F1 ヒートマップ ---
vmax_f1 = 1.0
im1 = ax1.imshow(f1_data, aspect="auto", cmap="Blues",
                  vmin=0, vmax=vmax_f1)
for i in range(len(shapes)):
    for j in range(len(f1_methods)):
        val = f1_data[i, j]
        color = "white" if val > vmax_f1 * 0.55 else "black"
        ax1.text(j, i, f"{val:.3f}", ha="center", va="center",
                 fontsize=8, fontweight="bold", color=color)

ax1.set_xticks(range(len(f1_methods)))
ax1.set_xticklabels(f1_methods, fontsize=7.5, rotation=35, ha="right")
ax1.set_yticks(range(len(shapes)))
ax1.set_yticklabels(shapes, fontsize=7.5)
ax1.set_title("(a) Pattern Detection (F1)", pad=6)
cbar1 = fig.colorbar(im1, ax=ax1, shrink=0.85, pad=0.03)
cbar1.ax.tick_params(labelsize=6.5)

# --- (b) mean Jaccard ヒートマップ ---
vmax_mj = 0.25
im2 = ax2.imshow(mj_data, aspect="auto", cmap="Blues",
                  vmin=0, vmax=vmax_mj)
for i in range(len(shapes)):
    for j in range(len(mj_methods)):
        val = mj_data[i, j]
        color = "white" if val > vmax_mj * 0.55 else "black"
        ax2.text(j, i, f"{val:.3f}", ha="center", va="center",
                 fontsize=8, fontweight="bold", color=color)

ax2.set_xticks(range(len(mj_methods)))
ax2.set_xticklabels(mj_methods, fontsize=7.5, rotation=35, ha="right")
ax2.set_yticks(range(len(shapes)))
ax2.set_yticklabels(shapes, fontsize=7.5)
ax2.set_title("(b) Region Recovery (mean Jaccard)", pad=6)
cbar2 = fig.colorbar(im2, ax=ax2, shrink=0.85, pad=0.03)
cbar2.ax.tick_params(labelsize=6.5)

fig.tight_layout(w_pad=2.0)

for ext in ("pdf", "png"):
    path = FIG_OUT / f"fig_ex1_heatmap.{ext}"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    for dest in PAPER_FIGS:
        shutil.copy(path, dest / f"fig_ex1_heatmap.{ext}")

plt.close(fig)
print(f"生成完了: fig_ex1_heatmap.pdf/png → {[str(p) for p in PAPER_FIGS]}")
