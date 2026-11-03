#!/usr/bin/env python3
"""
EX-4 CASAS Exploration: Run Apriori-Window with various (W, theta) combinations
and interpret patterns in terms of smart-home room activity.

Output: experiments/run/results/casas_exploration.md
"""

import subprocess
import json
import csv
import os
import io
import tempfile
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT      = Path(__file__).resolve().parents[2]
BIN       = ROOT / "apriori_window_1d" / "target" / "release" / "apriori_window_1d"
DATA_DIR  = ROOT / "dataset" / "casas"
OUT_DIR   = ROOT / "experiments" / "run" / "results"
OUT_MD    = OUT_DIR / "casas_exploration.md"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── dataset configs ────────────────────────────────────────────────────────────

DATASETS = {
    "hh113": {
        "file": DATA_DIR / "hh113_1h.txt",
        "start": datetime(2011, 6, 15, 1, 0, 0),
        "sensors": {1: "Bathroom", 2: "Bedroom", 3: "DiningRoom",
                    4: "Kitchen",  5: "LivingRoom", 6: "OutsideDoor", 7: "WorkArea"},
    },
    "mv001": {
        "file": DATA_DIR / "mv001_1h.txt",
        "start": datetime(2013, 7, 11, 7, 0, 0),
        "sensors": {1: "Bathroom", 2: "Bedroom", 3: "Kitchen",
                    4: "LaundryRoom", 5: "LivingRoom", 6: "Office", 7: "OutsideDoor"},
    },
}

# ── parameter grid ─────────────────────────────────────────────────────────────

PARAM_GRID = {
    "hh113": [
        # (W_hours, theta, max_len, label)
        (12,   5, 4, "W=12h(半日) θ=5"),
        (12,   8, 4, "W=12h(半日) θ=8"),
        (24,   5, 4, "W=24h(1日) θ=5"),
        (24,  10, 4, "W=24h(1日) θ=10"),
        (24,  15, 4, "W=24h(1日) θ=15"),
        (48,   8, 4, "W=48h(2日) θ=8"),
        (48,  15, 4, "W=48h(2日) θ=15"),
        (48,  20, 4, "W=48h(2日) θ=20"),
        (72,  10, 4, "W=72h(3日) θ=10"),
        (72,  20, 4, "W=72h(3日) θ=20"),
        (168,  5, 3, "W=168h(1週) θ=5"),
        (168, 10, 3, "W=168h(1週) θ=10"),
        (168, 20, 3, "W=168h(1週) θ=20"),
    ],
    "mv001": [
        (12,  10, 4, "W=12h(半日) θ=10"),
        (12,  15, 4, "W=12h(半日) θ=15"),
        (24,  10, 4, "W=24h(1日) θ=10"),
        (24,  20, 4, "W=24h(1日) θ=20"),
        (24,  30, 4, "W=24h(1日) θ=30"),
        (48,  15, 4, "W=48h(2日) θ=15"),
        (48,  25, 4, "W=48h(2日) θ=25"),
        (48,  40, 4, "W=48h(2日) θ=40"),
        (72,  20, 4, "W=72h(3日) θ=20"),
        (72,  40, 4, "W=72h(3日) θ=40"),
        (168, 10, 3, "W=168h(1週) θ=10"),
        (168, 30, 3, "W=168h(1週) θ=30"),
        (168, 60, 3, "W=168h(1週) θ=60"),
    ],
}

# ── helpers ────────────────────────────────────────────────────────────────────

def run_experiment(dataset_name, W, theta, max_len):
    """Run binary with given params, return list of pattern dicts."""
    ds = DATASETS[dataset_name]
    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = Path(tmpdir) / "patterns.csv"
        settings = {
            "input_file": {"dir": str(DATA_DIR), "file_name": ds["file"].name},
            "output_files": {"dir": tmpdir, "patterns_output_file_name": "patterns.csv"},
            "apriori_parameters": {"window_size": W, "min_support": theta, "max_length": max_len},
        }
        settings_path = Path(tmpdir) / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = subprocess.run([str(BIN), str(settings_path)],
                                capture_output=True, text=True, timeout=120)
        if not out_csv.exists():
            return [], result.stdout

        patterns = []
        with open(out_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # parse pattern_components: "[{1, 2, 3}]"
                nums = list(map(int, re.findall(r"\d+", row["pattern_components"])))
                intervals_raw = row.get("intervals", "")
                intervals = []
                for m in re.finditer(r"\((\d+),(\d+)\)", intervals_raw):
                    intervals.append((int(m.group(1)), int(m.group(2))))
                patterns.append({
                    "items": nums,
                    "size": int(row["pattern_size"]),
                    "n_intervals": int(row["intervals_count"]),
                    "intervals": intervals,
                })
        return patterns, result.stdout


def idx_to_date(ds_name, idx_h):
    start = DATASETS[ds_name]["start"]
    return start + timedelta(hours=int(idx_h))


def items_to_rooms(ds_name, items):
    smap = DATASETS[ds_name]["sensors"]
    return [smap.get(i, f"Sensor{i}") for i in items]


def interpret_pattern(ds_name, items, W_h, intervals):
    """Generate natural language interpretation."""
    rooms = items_to_rooms(ds_name, items)
    room_str = " + ".join(rooms)

    # Window semantics
    if W_h <= 12:
        window_desc = "半日（12時間）以内"
    elif W_h <= 24:
        window_desc = "1日以内"
    elif W_h <= 48:
        window_desc = "2日以内"
    elif W_h <= 72:
        window_desc = "3日以内"
    else:
        window_desc = "1週間以内"

    # Behavioural inference by room combination
    room_set = set(rooms)
    if {"Bathroom", "Bedroom"} <= room_set:
        behaviour = "起床・就寝ルーティン"
    elif {"Kitchen", "DiningRoom"} <= room_set:
        behaviour = "食事準備・食事行動"
    elif {"Kitchen", "LivingRoom"} <= room_set:
        behaviour = "調理後のリビング滞在"
    elif {"Kitchen", "DiningRoom", "LivingRoom"} <= room_set:
        behaviour = "食事〜リビング移動ルーティン"
    elif {"Bathroom", "Kitchen"} <= room_set:
        behaviour = "朝の身支度（洗面→調理）"
    elif {"Bedroom", "Kitchen"} <= room_set:
        behaviour = "就寝前・起床直後の行動"
    elif {"LivingRoom", "Bedroom"} <= room_set:
        behaviour = "就寝前リビング→寝室移動"
    elif {"OutsideDoor"} <= room_set:
        behaviour = "外出・帰宅を含む行動"
    elif {"WorkArea"} <= room_set or {"Office"} <= room_set:
        behaviour = "在宅作業パターン"
    elif {"LaundryRoom"} <= room_set:
        behaviour = "洗濯行動"
    elif len(rooms) == 1:
        behaviour = f"{rooms[0]}の継続的な利用"
    else:
        behaviour = "複合的な居住行動"

    # Dense interval stats
    if intervals:
        start_dt = idx_to_date(ds_name, intervals[0][0])
        end_dt   = idx_to_date(ds_name, intervals[-1][1])
        durations = [(e - s) for s, e in intervals]
        avg_dur = sum(durations) / len(durations)
        max_dur = max(durations)
        interpretation = (
            f"**{room_str}**（{window_desc}で共起）\n"
            f"  - 推定行動: {behaviour}\n"
            f"  - 密集区間数: {len(intervals)}\n"
            f"  - 最初の密集開始: {start_dt.strftime('%Y-%m-%d')}\n"
            f"  - 最後の密集終了: {end_dt.strftime('%Y-%m-%d')}\n"
            f"  - 平均密集持続: {avg_dur:.1f}h、最大: {max_dur}h\n"
        )
    else:
        interpretation = f"**{room_str}** — 区間なし\n"

    return interpretation, behaviour


def top_patterns(patterns, n=5):
    """Return top-n by n_intervals, prefer larger itemsets as tiebreak."""
    return sorted(patterns, key=lambda p: (p["n_intervals"], p["size"]), reverse=True)[:n]


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    lines = ["# CASAS EX-4 探索実験レポート\n",
             f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
             "---\n"]

    for ds_name in ["hh113", "mv001"]:
        ds_info = DATASETS[ds_name]
        lines.append(f"## データセット: {ds_name}\n\n")
        lines.append(f"- センサ: {', '.join(f'{k}={v}' for k,v in ds_info['sensors'].items())}\n")
        lines.append(f"- 期間: {ds_info['start'].strftime('%Y-%m-%d')} 〜\n")
        lines.append(f"- Tランザクション数: {12226 if ds_name=='hh113' else 34759}\n\n")

        grid = PARAM_GRID[ds_name]
        for W, theta, max_len, label in grid:
            print(f"Running {ds_name} {label} ...", flush=True)
            patterns, stdout = run_experiment(ds_name, W, theta, max_len)

            lines.append(f"### {label}  (max_len={max_len})\n\n")
            lines.append(f"- **パターン総数**: {len(patterns)}\n")

            if not patterns:
                lines.append("- 結果なし（閾値が高すぎる可能性）\n\n")
                continue

            # Size breakdown
            from collections import Counter
            size_count = Counter(p["size"] for p in patterns)
            lines.append(f"- サイズ別: " + ", ".join(f"k={k}: {v}件" for k,v in sorted(size_count.items())) + "\n\n")

            lines.append("#### 上位パターン（密集区間数順）\n\n")
            for i, pat in enumerate(top_patterns(patterns, n=6), 1):
                interp, beh = interpret_pattern(ds_name, pat["items"], W, pat["intervals"])
                lines.append(f"{i}. {interp}\n")

            # Interesting: smallest-size patterns with many intervals (recurrent routines)
            size1 = [p for p in patterns if p["size"] == 1]
            size2 = [p for p in patterns if p["size"] == 2]
            size3 = [p for p in patterns if p["size"] >= 3]

            if size2:
                best_pair = max(size2, key=lambda p: p["n_intervals"])
                rooms = items_to_rooms(ds_name, best_pair["items"])
                lines.append(f"**最頻ペア**: {' + '.join(rooms)} ({best_pair['n_intervals']} 区間)\n\n")

            if size3:
                best_multi = max(size3, key=lambda p: (p["n_intervals"], p["size"]))
                rooms = items_to_rooms(ds_name, best_multi["items"])
                lines.append(f"**最頻複合パターン (k≥3)**: {' + '.join(rooms)} ({best_multi['n_intervals']} 区間)\n\n")

            lines.append("---\n\n")

    # Summary: flag most interpretable
    lines.append("## 総評・自然な解釈候補\n\n")
    lines.append("各設定で得られた「推定行動」が特定の生活ルーティンに強く対応するものをまとめる。\n\n")
    lines.append("選定基準:\n- 密集区間数が多い（パターンが繰り返し出現）\n"
                 "- 複数センサが含まれる（行動遷移が見える）\n"
                 "- 区間の持続時間が短い（ルーティン的）\n\n")
    lines.append("→ 上記表から選択して論文 EX-4 分析に採用する\n")

    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"\n✓ 完了: {OUT_MD}")


if __name__ == "__main__":
    main()
