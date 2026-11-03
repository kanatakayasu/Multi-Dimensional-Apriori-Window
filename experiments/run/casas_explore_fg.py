#!/usr/bin/env python3
"""
CASAS Fine-Grain Exploration: W ≤ 6h, resolutions 15min / 30min / 1h
Output: experiments/run/results/casas_fg_exploration.md
"""

import subprocess, json, csv, os, io, tempfile, re
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
BIN      = ROOT / "apriori_window_1d" / "target" / "release" / "apriori_window_1d"
DATA_DIR = ROOT / "dataset" / "casas"
OUT_DIR  = ROOT / "experiments" / "run" / "results"
OUT_MD   = OUT_DIR / "casas_fg_exploration.md"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── sensor maps ──────────────────────────────────────────────────────────────

SENSORS = {
    "hh113": {1:"Bathroom", 2:"Bedroom", 3:"DiningRoom",
              4:"Kitchen",  5:"LivingRoom", 6:"OutsideDoor", 7:"WorkArea"},
    "mv001": {1:"Bathroom", 2:"Bedroom", 3:"Kitchen",
              4:"LaundryRoom", 5:"LivingRoom", 6:"Office", 7:"OutsideDoor"},
}

DATASET_START = {
    "hh113": datetime(2011, 6, 15, 1, 0, 0),
    "mv001": datetime(2013, 7, 11, 7, 0, 0),
}

def data_file(house, slot_hours):
    return DATA_DIR / f"{house}_{slot_hours}h.txt"

# ── parameter grid (slot_hours, W_hours, theta, max_len) ────────────────────
# θ は概ね W_slots × 30〜50% を目安に設定。
# W_max = 6h

PARAM_GRID = {
    "hh113": [
        # --- 15min (slot=0.25h) ---
        (0.25, 2,  3, 4),   # W=8slots,  θ=3  (38%)
        (0.25, 2,  5, 4),   # W=8slots,  θ=5  (63%) 上限確認用
        (0.25, 4,  5, 4),   # W=16slots, θ=5  (31%)
        (0.25, 4,  8, 4),   # W=16slots, θ=8  (50%)
        (0.25, 6,  7, 4),   # W=24slots, θ=7  (29%)
        (0.25, 6, 10, 4),   # W=24slots, θ=10 (42%)
        # --- 30min (slot=0.5h) ---
        (0.5,  2,  1, 4),   # W=4slots,  θ=1  (25%)
        (0.5,  2,  2, 4),   # W=4slots,  θ=2  (50%)
        (0.5,  4,  2, 4),   # W=8slots,  θ=2  (25%)
        (0.5,  4,  3, 4),   # W=8slots,  θ=3  (38%)
        (0.5,  6,  3, 4),   # W=12slots, θ=3  (25%)
        (0.5,  6,  5, 4),   # W=12slots, θ=5  (42%)
        # --- 1h (slot=1h) ---
        (1.0,  4,  1, 4),   # W=4slots,  θ=1  (25%)
        (1.0,  4,  2, 4),   # W=4slots,  θ=2  (50%)
        (1.0,  6,  2, 4),   # W=6slots,  θ=2  (33%)
        (1.0,  6,  3, 4),   # W=6slots,  θ=3  (50%)
    ],
    "mv001": [
        # --- 15min (slot=0.25h) ---
        (0.25, 2,  3, 4),
        (0.25, 2,  5, 4),
        (0.25, 4,  5, 4),
        (0.25, 4,  8, 4),
        (0.25, 6,  7, 4),
        (0.25, 6, 10, 4),
        # --- 30min (slot=0.5h) ---
        (0.5,  2,  1, 4),
        (0.5,  2,  2, 4),
        (0.5,  4,  2, 4),
        (0.5,  4,  3, 4),
        (0.5,  6,  3, 4),
        (0.5,  6,  5, 4),
        # --- 1h (slot=1h) ---
        (1.0,  4,  1, 4),
        (1.0,  4,  2, 4),
        (1.0,  6,  2, 4),
        (1.0,  6,  3, 4),
    ],
}

# ── helpers ──────────────────────────────────────────────────────────────────

def run_experiment(house, slot_hours, W_hours, theta, max_len):
    W_slots = round(W_hours / slot_hours)
    fp = data_file(house, slot_hours)
    if not fp.exists():
        return [], f"FILE NOT FOUND: {fp}"
    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = Path(tmpdir) / "patterns.csv"
        settings = {
            "input_file": {"dir": str(DATA_DIR), "file_name": fp.name},
            "output_files": {"dir": tmpdir, "patterns_output_file_name": "patterns.csv"},
            "apriori_parameters": {"window_size": W_slots, "min_support": theta, "max_length": max_len},
        }
        settings_path = Path(tmpdir) / "settings.json"
        settings_path.write_text(json.dumps(settings))
        result = subprocess.run([str(BIN), str(settings_path)],
                                capture_output=True, text=True, timeout=180)
        if not out_csv.exists():
            return [], result.stdout
        patterns = []
        with open(out_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nums = list(map(int, re.findall(r"\d+", row["pattern_components"])))
                intervals = []
                for m in re.finditer(r"\((\d+),(\d+)\)", row.get("intervals", "")):
                    intervals.append((int(m.group(1)), int(m.group(2))))
                patterns.append({
                    "items": nums,
                    "size": int(row["pattern_size"]),
                    "n_intervals": int(row["intervals_count"]),
                    "intervals": intervals,
                })
        return patterns, result.stdout


def idx_to_date(house, slot_idx, slot_hours):
    return DATASET_START[house] + timedelta(hours=slot_idx * slot_hours)


def interval_duration_hours(start_slot, end_slot, slot_hours):
    return (end_slot - start_slot) * slot_hours


def items_to_rooms(house, items):
    smap = SENSORS[house]
    return [smap.get(i, f"S{i}") for i in items]


def infer_behaviour(rooms):
    rs = set(rooms)
    if {"Bathroom", "Bedroom"} <= rs:              return "起床・就寝ルーティン"
    if {"Kitchen", "DiningRoom"} <= rs:            return "食事準備・食事行動"
    if {"Kitchen", "LivingRoom"} <= rs:            return "調理後リビング滞在"
    if {"Bathroom", "Kitchen"} <= rs:              return "朝の身支度（洗面→調理）"
    if {"Bedroom", "Kitchen"} <= rs:               return "就寝前・起床直後"
    if {"Bedroom", "LivingRoom"} <= rs:            return "就寝前リビング→寝室"
    if {"Bedroom", "Office"} <= rs:                return "在宅作業"
    if {"OutsideDoor"} <= rs:                      return "外出・帰宅パターン"
    if {"LaundryRoom"} <= rs:                      return "洗濯行動"
    if {"WorkArea"} <= rs:                         return "作業場利用"
    if len(rooms) == 1:                            return f"{rooms[0]}の継続的利用"
    return "複合居住行動"


def window_label(W_hours):
    if W_hours <= 1:   return "1時間以内"
    if W_hours <= 2:   return "2時間以内"
    if W_hours <= 4:   return "4時間以内"
    return "6時間以内"


def resolution_label(slot_hours):
    if slot_hours == 0.25: return "15分"
    if slot_hours == 0.5:  return "30分"
    return "1時間"


def format_pattern(house, pat, slot_hours, W_hours):
    rooms = items_to_rooms(house, pat["items"])
    behaviour = infer_behaviour(rooms)
    ivs = pat["intervals"]
    if not ivs:
        return f"**{' + '.join(rooms)}** — 区間なし\n"
    durations = [interval_duration_hours(s, e, slot_hours) for s, e in ivs]
    avg_d = sum(durations) / len(durations)
    max_d = max(durations)
    start_dt = idx_to_date(house, ivs[0][0], slot_hours)
    end_dt   = idx_to_date(house, ivs[-1][1], slot_hours)
    return (
        f"**{' + '.join(rooms)}**（{window_label(W_hours)}で共起）\n"
        f"  - 推定行動: {behaviour}\n"
        f"  - 密集区間数: {pat['n_intervals']}\n"
        f"  - 最初の密集開始: {start_dt.strftime('%Y-%m-%d')}\n"
        f"  - 最後の密集終了: {end_dt.strftime('%Y-%m-%d')}\n"
        f"  - 平均密集持続: {avg_d:.1f}h、最大: {max_d:.1f}h\n"
    )


# ── scoring: interpretability heuristic ──────────────────────────────────────
# ポイント: パターン数が10-40 / 平均密集持続が短い / k≥2多い

def score_config(patterns, slot_hours, W_hours):
    if not patterns:
        return -999
    n = len(patterns)
    # 理想パターン数: 10-40
    n_score = -abs(n - 20) / 20.0

    # 平均密集持続がW_hoursに近い（短すぎず長すぎず）
    all_ivs = [iv for p in patterns for iv in p["intervals"]]
    if all_ivs:
        durations = [interval_duration_hours(s, e, slot_hours) for s, e in all_ivs]
        avg_d = sum(durations) / len(durations)
        # 理想: 平均持続 ≈ W_hours × 1.5〜3
        ideal_d = W_hours * 2.0
        dur_score = -abs(avg_d - ideal_d) / ideal_d
    else:
        dur_score = -1

    # k≥2パターンの割合
    multi = sum(1 for p in patterns if p["size"] >= 2)
    multi_ratio = multi / n

    return n_score + dur_score + multi_ratio


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    lines = [
        "# CASAS Fine-Grain 探索実験レポート\n",
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "条件: W ≤ 6h、解像度 15min/30min/1h、hh113 & mv001\n\n",
        "---\n",
    ]

    summary_rows = []  # (house, slot_h, W_h, theta, n_patterns, score, best_pair, best_triple)

    for house in ["hh113", "mv001"]:
        lines.append(f"\n## データセット: {house}\n\n")
        lines.append(f"センサ: {', '.join(f'{k}={v}' for k,v in SENSORS[house].items())}\n\n")

        grid = PARAM_GRID[house]
        for slot_hours, W_hours, theta, max_len in grid:
            W_slots = round(W_hours / slot_hours)
            label = (f"{resolution_label(slot_hours)}刻み "
                     f"W={W_hours}h({W_slots}スロット) θ={theta}")
            print(f"  {house} {label} ...", flush=True)

            patterns, _stdout = run_experiment(house, slot_hours, W_hours, theta, max_len)
            score = score_config(patterns, slot_hours, W_hours)

            lines.append(f"### {label}\n\n")
            lines.append(f"- **パターン総数**: {len(patterns)}\n")

            if not patterns:
                lines.append("- 結果なし（θが高すぎる可能性）\n\n---\n\n")
                summary_rows.append((house, slot_hours, W_hours, theta, 0, score, "–", "–"))
                continue

            size_cnt = Counter(p["size"] for p in patterns)
            lines.append(f"- サイズ別: " +
                         ", ".join(f"k={k}: {v}件" for k, v in sorted(size_cnt.items())) + "\n")
            lines.append(f"- **解釈性スコア**: {score:.3f}\n\n")

            top = sorted(patterns, key=lambda p: (p["n_intervals"], p["size"]), reverse=True)[:6]
            lines.append("#### 上位パターン（密集区間数順）\n\n")
            for i, pat in enumerate(top, 1):
                lines.append(f"{i}. {format_pattern(house, pat, slot_hours, W_hours)}\n")

            pairs   = [p for p in patterns if p["size"] == 2]
            triples = [p for p in patterns if p["size"] >= 3]
            best_pair   = max(pairs,   key=lambda p: p["n_intervals"]) if pairs   else None
            best_triple = max(triples, key=lambda p: p["n_intervals"]) if triples else None

            bp_str = " + ".join(items_to_rooms(house, best_pair["items"])) + f" ({best_pair['n_intervals']}区間)" if best_pair else "–"
            bt_str = " + ".join(items_to_rooms(house, best_triple["items"])) + f" ({best_triple['n_intervals']}区間)" if best_triple else "–"

            if best_pair:
                lines.append(f"**最頻ペア**: {bp_str}\n\n")
            if best_triple:
                lines.append(f"**最頻複合パターン**: {bt_str}\n\n")
            lines.append("---\n\n")

            summary_rows.append((house, slot_hours, W_hours, theta,
                                  len(patterns), score, bp_str, bt_str))

    # ── サマリーテーブル ──────────────────────────────────────────────────────
    lines.append("\n---\n\n## サマリー（解釈性スコア順）\n\n")
    lines.append("| データ | 解像度 | W | θ | パターン数 | スコア | 最頻ペア |\n")
    lines.append("|--------|--------|---|---|-----------|--------|----------|\n")
    for row in sorted(summary_rows, key=lambda r: r[5], reverse=True):
        house, sh, Wh, th, n, sc, bp, bt = row
        lines.append(f"| {house} | {resolution_label(sh)} | {Wh}h | {th} | {n} | {sc:.3f} | {bp} |\n")

    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"\n完了: {OUT_MD}")

    # ── 推奨設定を表示 ────────────────────────────────────────────────────────
    print("\n=== 推奨設定（スコア上位3） ===")
    for row in sorted(summary_rows, key=lambda r: r[5], reverse=True)[:6]:
        house, sh, Wh, th, n, sc, bp, _ = row
        print(f"  {house} | {resolution_label(sh)} W={Wh}h θ={th} → {n}パターン score={sc:.3f}")
        print(f"    最頻ペア: {bp}")


if __name__ == "__main__":
    main()
