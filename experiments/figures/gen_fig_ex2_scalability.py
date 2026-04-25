#!/usr/bin/env python3
"""EX-2 スケーラビリティを log-log プロットで可視化する。"""

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FIG_OUT = SCRIPT_DIR / "figures"
PAPER_FIG = SCRIPT_DIR.parent / "paper" / "DSAA2026" / "fig"
FIG_OUT.mkdir(parents=True, exist_ok=True)
PAPER_FIG.mkdir(parents=True, exist_ok=True)

with open(SCRIPT_DIR / "results" / "ex2_v4" / "ex2_v4_results.json") as f:
    data = json.load(f)

results = [r for r in data["part_a"] if r.get("run_s", -1) > 0]

plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "cm",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "axes.linewidth": 0.6,
})

fig, ax = plt.subplots(figsize=(3.4, 2.8))

# T/s 比率でグループ化して色分け
# 各点を s の値で色分け
s_vals = sorted(set(r["s_max"] for r in results))
markers = ["o", "s", "D", "^"]
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

for idx, s in enumerate(s_vals):
    subset = [r for r in results if r["s_max"] == s]
    subset.sort(key=lambda r: r["n_txn"])
    ns = [r["n_txn"] for r in subset]
    ts = [r["run_s"] for r in subset]
    ax.plot(ns, ts, marker=markers[idx], color=colors[idx],
            markersize=5, linewidth=1.2, label=f"$s={s:,}$".replace(",", "{,}"))

# 理想的な線形参照線
n_ref = np.array([1e3, 1e8])
t_ref = n_ref * (0.009 / 1e3)  # N=1000 で 0.009s を基準
ax.plot(n_ref, t_ref, "k--", linewidth=0.8, alpha=0.4, label="linear ref.")

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("$N$ (number of transactions)")
ax.set_ylabel("Runtime (s)")
ax.legend(fontsize=7, loc="upper left", framealpha=0.9)
ax.grid(True, which="both", linewidth=0.3, alpha=0.5)
ax.set_xlim(5e2, 2e8)
ax.set_ylim(5e-3, 1e3)

fig.tight_layout()

import shutil
for ext in ("pdf", "png"):
    path = FIG_OUT / f"fig_ex2_scalability.{ext}"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    shutil.copy(path, PAPER_FIG / f"fig_ex2_scalability.{ext}")

plt.close(fig)
print(f"生成完了: fig_ex2_scalability.pdf/png → {PAPER_FIG}")
