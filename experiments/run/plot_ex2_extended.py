#!/usr/bin/env python3
"""
EX-2 Extended: scalability bar charts (runtime + peak memory, dual y-axis)
Output: paper/DSAA2026_eng/fig/fig_ex2_scalability.pdf
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = REPO_ROOT / "experiments" / "results" / "ex2_extended" / "results.json"
OUT_PDF  = REPO_ROOT / "paper" / "DSAA2026_eng" / "fig" / "fig_ex2_scalability.pdf"
OUT_PDF2 = REPO_ROOT / "experiments" / "results" / "ex2_extended" / "fig_ex2_scalability.pdf"

with open(RESULTS) as f:
    data = json.load(f)

# ---------------------------------------------------------------------------
# Style – match fig_ex1_heatmap (Blues palette, dejavusans math font)
# ---------------------------------------------------------------------------
COLOR_T = "#08306b"   # navy (紺色) – Runtime
COLOR_M = "#6baed6"   # blue       – Peak RSS
ALPHA   = 0.90
W       = 0.40        # bar width (no gap; each x-pos has two touching bars)

plt.rcParams.update({
    "text.usetex":       True,
    "font.family":       "serif",
    "font.serif":        ["Computer Modern Roman"],
    "font.size":         11,
    "axes.labelsize":    11,
    "axes.titlesize":    11,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "axes.linewidth":    0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
})


# ---------------------------------------------------------------------------
# Axis configurator
# ---------------------------------------------------------------------------

def _set_axis(ax, scale, ticks, top, color, fmt="plain"):
    if scale == "log":
        ax.set_yscale("log")
        ax.set_yticks(ticks)
        if fmt == "power":
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(
                lambda v, _: r"$10^{%d}$" % int(round(np.log10(v))) if v > 0 else "0"
            ))
        else:
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    else:
        ax.set_yticks(ticks)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_ylim(top=top)
    ax.yaxis.set_minor_locator(ticker.NullLocator())
    ax.tick_params(axis="y", labelcolor=color)


# ---------------------------------------------------------------------------
# Panel drawing
# ---------------------------------------------------------------------------

def draw_panel(ax, x, ts, ms,
               t_scale, t_ticks, t_top,
               m_scale, m_ticks, m_top,
               title, xlabel=None, xlabels=None, xfont=8,
               t_fmt="plain", m_fmt="plain"):

    ax2 = ax.twinx()

    # Adjacent bars (no gap)
    ax.bar( x - W / 2, ts, W, color=COLOR_T, alpha=ALPHA, zorder=3)
    ax2.bar(x + W / 2, ms, W, color=COLOR_M, alpha=ALPHA, zorder=3)

    _set_axis(ax,  t_scale, t_ticks, t_top, COLOR_T, fmt=t_fmt)
    _set_axis(ax2, m_scale, m_ticks, m_top, COLOR_M, fmt=m_fmt)

    ax.set_ylabel("Runtime (s)",  color=COLOR_T)
    ax2.set_ylabel("Peak RSS (MB)", color=COLOR_M)

    if xlabels is not None:
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, fontsize=xfont)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.set_title(title)

    # Despine
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6))
(ax_a, ax_b), (ax_c, ax_d) = axes

# (a) T-scalability: exclude N=10^8
ea  = data["exp_a"][:4]
x_a = np.arange(len(ea), dtype=float)
draw_panel(
    ax_a, x_a,
    ts=[r["elapsed_s"]   for r in ea],
    ms=[r["peak_rss_mb"] for r in ea],
    t_scale="log",  t_ticks=[1, 10, 100],              t_top=100,
    m_scale="log",  m_ticks=[1, 10, 100, 1000, 10000], m_top=10000,
    m_fmt="power",
    title="(a) $T$-scalability ($S{=}100$)",
    xlabel="$N = T \\times S$",
    xlabels=[r"$10^{%d}$" % int(round(np.log10(r["n_txn"]))) for r in ea],
)

# (b) S-scalability
eb  = data["exp_b"]
x_b = np.arange(len(eb), dtype=float)
draw_panel(
    ax_b, x_b,
    ts=[r["elapsed_s"]   for r in eb],
    ms=[r["peak_rss_mb"] for r in eb],
    t_scale="log",  t_ticks=[0.1, 1, 10, 100],         t_top=100,
    m_scale="log",  m_ticks=[1, 10, 100, 1000, 10000],  m_top=10000,
    m_fmt="power",
    title="(b) $S$-scalability ($T{=}1000$)",
    xlabel="$N = T \\times S$",
    xlabels=[r"$10^{%d}$" % int(round(np.log10(r["n_txn"]))) for r in eb],
)

# (c) d-scalability (N fixed ≈ 10^5)
ec  = data["exp_c"]
x_c = np.arange(len(ec), dtype=float)
draw_panel(
    ax_c, x_c,
    ts=[r["elapsed_s"]   for r in ec],
    ms=[r["peak_rss_mb"] for r in ec],
    t_scale="linear", t_ticks=[0, 1, 2, 3],  t_top=3.0,
    m_scale="linear", m_ticks=[0, 25, 50],   m_top=50,
    title="(c) $d$-scalability ($N{\\approx}10^5$)",
    xlabels=["$d{=}%d$" % r["d"] for r in ec],
    xfont=9,
)

# (d) |I|-scalability: 20, 40, 60, 80
ed  = [r for r in data["exp_d"] if 20 <= r["n_items"] <= 80]
x_d = np.arange(len(ed), dtype=float)
draw_panel(
    ax_d, x_d,
    ts=[r["elapsed_s"]   for r in ed],
    ms=[r["peak_rss_mb"] for r in ed],
    t_scale="linear", t_ticks=[0, 5, 10],  t_top=10,
    m_scale="linear", m_ticks=[0, 25, 50], m_top=50,
    title="(d) $|\\mathcal{I}|$-scalability ($T{=}1000,\\,S{=}100$)",
    xlabel="$|\\mathcal{I}|$",
    xlabels=[str(r["n_items"]) for r in ed],
)

# ---------------------------------------------------------------------------
# Shared legend
# ---------------------------------------------------------------------------
handles = [
    Patch(color=COLOR_T, alpha=ALPHA, label="Runtime (s)"),
    Patch(color=COLOR_M, alpha=ALPHA, label="Peak RSS (MB)"),
]
fig.legend(handles=handles, loc="lower center", ncol=2,
           bbox_to_anchor=(0.5, -0.01), frameon=False, fontsize=9)

fig.tight_layout(rect=[0, 0.06, 1, 1])

for out in [OUT_PDF, OUT_PDF2]:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", dpi=200)
    print(f"Saved: {out}")
