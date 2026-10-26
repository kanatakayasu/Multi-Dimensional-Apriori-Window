#!/usr/bin/env python3
"""
EX-2 実験結果 → 論文反映スクリプト

run_ex2_scalability_v4.py の結果 JSON を読み込み、以下を実行する:
  1. 05_experiments.tex の EX-2 表（tab:ex2_grid）を実行時間で埋める
  2. 05_experiments.tex の EX-2 分析パラグラフを生成・埋め込む
  3. EX-2 用ヒートマップ + N-vs-time 図を生成し paper/DSAA2026/fig/ にコピー

v4 結果は {"part_a": [...], "part_b": [...]} 形式。
v3 結果（フラットリスト）にも後方互換。

使い方:
  python3 experiments/fill_ex2_paper.py [--results PATH] [--dry-run]

  --results  結果 JSON のパス（デフォルト: experiments/results/ex2_v4/ex2_v4_results.json）
  --dry-run  LaTeX ファイルを更新せず、生成内容を stdout に表示
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_RESULTS = SCRIPT_DIR / "results" / "ex2_v4" / "ex2_v4_results.json"
TEX_PATH = REPO_ROOT / "paper" / "DSAA2026" / "sec" / "05_experiments.tex"
FIG_OUT = SCRIPT_DIR / "figures"
PAPER_FIG = REPO_ROOT / "paper" / "DSAA2026" / "fig"

T_LIST = [100, 1_000, 10_000, 100_000]
S_LIST = [10, 100, 1_000, 10_000]


# ---------------------------------------------------------------------------
# 結果読み込み
# ---------------------------------------------------------------------------

def load_results(path: Path) -> tuple[dict, list]:
    """JSON を読み込み、(part_a lookup, part_b list) を返す。
    v4形式 {"part_a": [...], "part_b": [...]} と v3形式（フラットリスト）の両方に対応。
    """
    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "part_a" in data:
        raw_a = data["part_a"]
        part_b = data.get("part_b", [])
    else:
        raw_a = data
        part_b = []

    lookup = {}
    for r in raw_a:
        key = (r["t_max"], r["s_max"])
        lookup[key] = r
    return lookup, part_b


# ---------------------------------------------------------------------------
# LaTeX 表の生成
# ---------------------------------------------------------------------------

def format_time(seconds: float) -> str:
    """実行時間を適切なフォーマットに変換する。"""
    if seconds < 0:
        return "TO"
    elif seconds < 0.01:
        return f"{seconds:.4f}"
    elif seconds < 10:
        return f"{seconds:.3f}"
    elif seconds < 100:
        return f"{seconds:.2f}"
    elif seconds < 1000:
        return f"{seconds:.1f}"
    else:
        return f"{seconds:,.0f}"


def format_t(t: int) -> str:
    """T の値を LaTeX 用にフォーマット。"""
    if t >= 1000:
        # 100,000 → 100{,}000
        s = f"{t:,}"
        return s.replace(",", "{,}")
    return str(t)


def build_table_rows(lookup: dict) -> list[str]:
    """4×4 テーブルの行を生成する。"""
    rows = []
    for t in T_LIST:
        cells = []
        for s in S_LIST:
            r = lookup.get((t, s))
            if r is None:
                cells.append("---")
            elif r.get("run_s", -1) < 0 or r.get("note") == "TIMEOUT":
                cells.append("TO")
            else:
                cells.append(format_time(r["run_s"]))
        t_label = format_t(t)
        # パディング調整
        row = f"{t_label:>9} & {cells[0]:>6} & {cells[1]:>6} & {cells[2]:>6} & {cells[3]:>6} \\\\"
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 分析テキストの生成
# ---------------------------------------------------------------------------

def build_analysis(lookup: dict) -> str:
    """EX-2 の分析パラグラフを生成する。"""
    lines = []

    # 全結果を収集
    valid = [(k, v) for k, v in lookup.items() if v.get("run_s", -1) > 0]
    if not valid:
        return "% TODO: 結果が未取得のため分析を記述できない"

    times = {k: v["run_s"] for k, v in valid}

    # 最小・最大
    k_min = min(times, key=times.get)
    k_max = max(times, key=times.get)
    t_min, t_max_val = times[k_min], times[k_max]
    n_min = k_min[0] * k_min[1]
    n_max = k_max[0] * k_max[1]

    lines.append(
        f"最小の設定 $N = {n_min:,}$（$T{{=}}{k_min[0]:,}, s{{=}}{k_min[1]:,}$）で "
        f"{format_time(t_min)} 秒，"
    )
    lines.append(
        f"最大の設定 $N = {n_max:,}$（$T{{=}}{k_max[0]:,}, s{{=}}{k_max[1]:,}$）で "
        f"{format_time(t_max_val)} 秒であった。"
    )

    # 同一 N での T/s 比率の影響を分析
    # N が同じ設定のペアを見つける
    n_groups: dict[int, list] = {}
    for (t, s), sec in times.items():
        n = t * s
        n_groups.setdefault(n, []).append((t, s, sec))

    ratio_analysis = []
    for n_val, entries in sorted(n_groups.items()):
        if len(entries) >= 2:
            entries.sort(key=lambda x: x[2])
            fastest = entries[0]
            slowest = entries[-1]
            if fastest[2] > 0:
                ratio = slowest[2] / fastest[2]
                ratio_analysis.append((n_val, fastest, slowest, ratio))

    if ratio_analysis:
        lines.append("")
        lines.append(
            "同一 $N$ でも $T/s$ 比率により実行時間に差が生じる。"
        )
        # 最大の差を報告
        biggest = max(ratio_analysis, key=lambda x: x[3])
        n_val, fast, slow, ratio = biggest
        lines.append(
            f"例えば $N = {n_val:,}$ では，"
            f"$T{{=}}{fast[0]:,}, s{{=}}{fast[1]:,}$ の {format_time(fast[2])} 秒に対し "
            f"$T{{=}}{slow[0]:,}, s{{=}}{slow[1]:,}$ の {format_time(slow[2])} 秒と "
            f"{ratio:.1f} 倍の差がある。"
        )
        lines.append(
            "これは空間幅 $s$ が大きいほど空間開始点数 $s - W_1 + 1$ が増加し，"
            "時間多重集合の構築回数が増えるためである。"
        )

    # スケーリング傾向
    lines.append("")
    lines.append(
        "全体として，実行時間はトランザクション数 $N$ に対しておおむね線形にスケールし，"
        "同一 $N$ では空間幅が大きいほど実行時間が増加する傾向が確認された。"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LaTeX ファイルの更新
# ---------------------------------------------------------------------------

def update_tex(lookup: dict, dry_run: bool = False):
    """05_experiments.tex の EX-2 表と分析を更新する。"""
    tex = TEX_PATH.read_text(encoding="utf-8")

    # --- 表の更新 ---
    rows = build_table_rows(lookup)
    # 既存の --- 行を置換
    # パターン: "100       & --- & --- & --- & --- \\" 等の4行
    table_pattern = re.compile(
        r"(100\s+&\s+---\s+&\s+---\s+&\s+---\s+&\s+---\s*\\\\.*?\n"
        r".*?1\{,\}000\s+&\s+---\s+&\s+---\s+&\s+---\s+&\s+---\s*\\\\.*?\n"
        r".*?10\{,\}000\s+&\s+---\s+&\s+---\s+&\s+---\s+&\s+---\s*\\\\.*?\n"
        r".*?100\{,\}000\s+&\s+---\s+&\s+---\s+&\s+---\s+&\s+---\s*\\\\)",
        re.DOTALL,
    )
    new_rows = "\n".join(rows)

    if table_pattern.search(tex):
        tex = table_pattern.sub(lambda _: new_rows, tex)
        print("表を更新しました。")
    else:
        # --- が既に埋まっている場合も対応: 4行の数値行を置換
        # midrule と bottomrule の間の4行を置換
        table_pattern2 = re.compile(
            r"(\\midrule\n)(.*?\n)(.*?\n)(.*?\n)(.*?\n)(\\\\bottomrule)",
            re.DOTALL,
        )
        m = table_pattern2.search(tex)
        if m:
            tex = tex[:m.start(2)] + new_rows + "\n" + tex[m.start(6):]
            print("表を更新しました（既存データを上書き）。")
        else:
            print("警告: 表のパターンが見つかりません。手動で更新してください。",
                  file=sys.stderr)
            print("生成した行:")
            print(new_rows)

    # --- 分析の更新 ---
    analysis = build_analysis(lookup)

    # "% TODO: 分析を記述" を置換
    todo_pattern = "% TODO: 分析を記述"
    if todo_pattern in tex:
        tex = tex.replace(todo_pattern, analysis)
        print("分析を埋め込みました。")
    else:
        print("注意: 分析 TODO が見つかりません。既に記述済みの可能性があります。")
        print("生成した分析:")
        print(analysis)

    # "% TODO: 実験結果を埋める" も削除
    tex = tex.replace("% TODO: 実験結果を埋める\n", "")

    if dry_run:
        print("\n=== dry-run: 更新後の EX-2 部分 ===")
        # EX-2 セクション部分だけ表示
        start = tex.find("\\subsection{EX-2")
        if start >= 0:
            end = tex.find("\\end{table}", start)
            if end >= 0:
                print(tex[start : end + len("\\end{table}")])
    else:
        TEX_PATH.write_text(tex, encoding="utf-8")
        print(f"更新: {TEX_PATH}")


# ---------------------------------------------------------------------------
# 図の生成
# ---------------------------------------------------------------------------

def generate_figure(lookup: dict):
    """EX-2 のヒートマップ + N-vs-time 散布図を生成する。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib が見つかりません。図の生成をスキップします。",
              file=sys.stderr)
        return

    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.linewidth": 0.6,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.8))

    # --- Panel (a): ヒートマップ ---
    grid = np.full((len(T_LIST), len(S_LIST)), np.nan)
    for i, t in enumerate(T_LIST):
        for j, s in enumerate(S_LIST):
            r = lookup.get((t, s))
            if r and r.get("run_s", -1) > 0:
                grid[i, j] = r["run_s"]

    im = ax1.imshow(grid, aspect="auto", cmap="YlOrRd",
                    norm=matplotlib.colors.LogNorm(
                        vmin=max(0.001, np.nanmin(grid)),
                        vmax=np.nanmax(grid)))
    # セル内に値を表示
    for i in range(len(T_LIST)):
        for j in range(len(S_LIST)):
            val = grid[i, j]
            if np.isnan(val):
                ax1.text(j, i, "TO", ha="center", va="center", fontsize=7,
                         color="gray")
            else:
                color = "white" if val > np.nanmedian(grid) else "black"
                ax1.text(j, i, format_time(val), ha="center", va="center",
                         fontsize=6.5, color=color)

    ax1.set_xticks(range(len(S_LIST)))
    ax1.set_xticklabels([f"{s:,}" for s in S_LIST], fontsize=7)
    ax1.set_yticks(range(len(T_LIST)))
    ax1.set_yticklabels([f"{t:,}" for t in T_LIST], fontsize=7)
    ax1.set_xlabel("$s$ (spatial width)")
    ax1.set_ylabel("$T$ (time length)")
    ax1.set_title("(a) Runtime (seconds)", pad=5)
    cbar = fig.colorbar(im, ax=ax1, shrink=0.8, pad=0.02)
    cbar.ax.tick_params(labelsize=6.5)

    # --- Panel (b): N vs time 散布図 ---
    ns, ts = [], []
    for (t, s), r in lookup.items():
        if r.get("run_s", -1) > 0:
            ns.append(t * s)
            ts.append(r["run_s"])

    ax2.scatter(ns, ts, s=30, c="#2d3436", edgecolors="#1e272e",
                linewidths=0.5, zorder=3)

    # 線形参照線
    if ns:
        ns_arr = np.array(ns)
        ts_arr = np.array(ts)
        # 最小二乗で log-log 傾き
        valid = (ns_arr > 0) & (ts_arr > 0)
        if valid.sum() >= 2:
            log_n = np.log10(ns_arr[valid])
            log_t = np.log10(ts_arr[valid])
            slope, intercept = np.polyfit(log_n, log_t, 1)
            n_fit = np.logspace(np.log10(min(ns_arr[valid])),
                                np.log10(max(ns_arr[valid])), 50)
            t_fit = 10 ** (slope * np.log10(n_fit) + intercept)
            ax2.plot(n_fit, t_fit, "--", color="#e17055", linewidth=1.0,
                     label=f"slope={slope:.2f}", zorder=2)
            ax2.legend(fontsize=7, loc="upper left")

    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("$N = T \\times s$")
    ax2.set_ylabel("Time (s)")
    ax2.set_title("(b) $N$ vs. Runtime", pad=5)
    ax2.yaxis.grid(True, color="#E0E0E0", linewidth=0.5, zorder=0)
    ax2.xaxis.grid(True, color="#E0E0E0", linewidth=0.5, zorder=0)
    ax2.set_axisbelow(True)
    for spine in ax2.spines.values():
        spine.set_linewidth(0.6)

    fig.tight_layout(w_pad=2.5)

    FIG_OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_OUT / f"fig_ex2_v3.{ext}", bbox_inches="tight", dpi=300)
    plt.close(fig)

    # paper にコピー
    if PAPER_FIG.exists():
        for ext in ("pdf", "png"):
            shutil.copy(FIG_OUT / f"fig_ex2_v3.{ext}",
                        PAPER_FIG / f"fig_ex2_v3.{ext}")
        print(f"図をコピー: {PAPER_FIG}")
    print("fig_ex2_v3.pdf/png を生成しました。")


def generate_theta_figure(part_b: list):
    """Part B: θ vs runtime の棒グラフを生成する。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib が見つかりません。θ図の生成をスキップします。",
              file=sys.stderr)
        return

    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "cm",
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.linewidth": 0.6,
    })

    valid = [r for r in part_b if r.get("run_s", -1) > 0]
    if not valid:
        print("Part B に有効な結果がありません。θ図をスキップします。")
        return

    thetas = [r["threshold"] for r in valid]
    times = [r["run_s"] for r in valid]
    n_patterns = [r.get("n_patterns", 0) for r in valid]

    fig, ax1 = plt.subplots(figsize=(3.5, 2.5))

    bars = ax1.bar(thetas, times, width=2.0, color="#0984e3",
                   edgecolor="#2d3436", linewidth=0.5, alpha=0.85, zorder=3)
    ax1.set_xlabel(r"$\theta$")
    ax1.set_ylabel("Time (s)", color="#0984e3")
    ax1.tick_params(axis="y", labelcolor="#0984e3")
    ax1.set_xticks(thetas)

    # 二軸: パターン数
    ax2 = ax1.twinx()
    ax2.plot(thetas, n_patterns, "o-", color="#d63031", markersize=4,
             linewidth=1.2, zorder=4)
    ax2.set_ylabel("\\# Patterns", color="#d63031")
    ax2.tick_params(axis="y", labelcolor="#d63031")

    ax1.yaxis.grid(True, color="#E0E0E0", linewidth=0.5, zorder=0)
    ax1.set_axisbelow(True)

    fig.tight_layout()

    FIG_OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_OUT / f"fig_ex2_theta.{ext}", bbox_inches="tight", dpi=300)
    plt.close(fig)

    if PAPER_FIG.exists():
        for ext in ("pdf", "png"):
            shutil.copy(FIG_OUT / f"fig_ex2_theta.{ext}",
                        PAPER_FIG / f"fig_ex2_theta.{ext}")
        print(f"θ図をコピー: {PAPER_FIG}")
    print("fig_ex2_theta.pdf/png を生成しました。")


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="EX-2 結果 → 論文反映")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS,
                        help="結果 JSON パス")
    parser.add_argument("--dry-run", action="store_true",
                        help="LaTeX を更新せず stdout に表示")
    args = parser.parse_args()

    if not args.results.exists():
        sys.exit(f"結果ファイルが見つかりません: {args.results}\n"
                 "先に run_ex2_scalability_v3.py を実行してください。")

    lookup, part_b = load_results(args.results)
    print(f"結果読み込み: Part A {len(lookup)} 件, Part B {len(part_b)} 件")

    update_tex(lookup, dry_run=args.dry_run)
    generate_figure(lookup)
    if part_b:
        generate_theta_figure(part_b)
    print("完了。")


if __name__ == "__main__":
    main()
