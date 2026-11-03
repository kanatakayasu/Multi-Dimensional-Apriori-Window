#!/usr/bin/env python3
"""
Round-2: hh113/mv001 fine-grain, higher θ to target 10-30 patterns
Also: 30min with higher θ, skip 1h (too small W)
"""

import subprocess, json, csv, tempfile, re
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
BIN      = ROOT / "apriori_window_1d" / "target" / "release" / "apriori_window_1d"
DATA_DIR = ROOT / "dataset" / "casas"
OUT_DIR  = ROOT / "experiments" / "run" / "results"
OUT_MD   = OUT_DIR / "casas_fg2_exploration.md"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

# ── 2nd round: higher θ ──────────────────────────────────────────────────────
# hh113 15min W=6h (24slots): θ=10 → 54pat  need θ=12~18 for ~15-25 pat
# hh113 15min W=4h (16slots): θ=8  → 67pat  need θ=10~14 for ~15-25 pat
# hh113 30min W=6h (12slots): θ=5  → 86pat  need θ=7~12
# hh113 30min W=4h (8slots):  θ=3  → 91pat  need θ=5~8
# mv001 15min W=6h (24slots): θ=10 → 91pat  need much higher θ (more data)
# mv001 15min W=4h (16slots): θ=8  → 91pat  need higher θ

PARAM_GRID = {
    "hh113": [
        # 15min W=6h
        (0.25, 6, 12, 4),
        (0.25, 6, 14, 4),
        (0.25, 6, 16, 4),
        (0.25, 6, 18, 4),
        # 15min W=4h
        (0.25, 4, 10, 4),
        (0.25, 4, 12, 4),
        (0.25, 4, 14, 4),
        # 30min W=6h
        (0.5,  6,  7, 4),
        (0.5,  6,  9, 4),
        (0.5,  6, 11, 4),
        # 30min W=4h
        (0.5,  4,  5, 4),
        (0.5,  4,  7, 4),
    ],
    "mv001": [
        # 15min W=6h (large dataset → scale θ up)
        (0.25, 6, 14, 4),
        (0.25, 6, 18, 4),
        (0.25, 6, 22, 4),
        # 15min W=4h
        (0.25, 4, 10, 4),
        (0.25, 4, 14, 4),
        (0.25, 4, 18, 4),
        # 30min W=6h
        (0.5,  6,  7, 4),
        (0.5,  6, 10, 4),
        (0.5,  6, 14, 4),
        # 30min W=4h
        (0.5,  4,  5, 4),
        (0.5,  4,  7, 4),
        (0.5,  4, 10, 4),
    ],
}

def run_experiment(house, slot_hours, W_hours, theta, max_len):
    W_slots = round(W_hours / slot_hours)
    fp = DATA_DIR / f"{house}_{slot_hours}h.txt"
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
            return []
        patterns = []
        with open(out_csv, newline="") as f:
            for row in csv.DictReader(f):
                nums = list(map(int, re.findall(r"\d+", row["pattern_components"])))
                intervals = [(int(m.group(1)), int(m.group(2)))
                             for m in re.finditer(r"\((\d+),(\d+)\)", row.get("intervals", ""))]
                patterns.append({
                    "items": nums, "size": int(row["pattern_size"]),
                    "n_intervals": int(row["intervals_count"]), "intervals": intervals,
                })
        return patterns

def idx_to_date(house, idx, slot_hours):
    return DATASET_START[house] + timedelta(hours=idx * slot_hours)

def items_to_rooms(house, items):
    return [SENSORS[house].get(i, f"S{i}") for i in items]

def infer_behaviour(rooms):
    rs = set(rooms)
    if {"Bathroom","Bedroom"} <= rs:    return "起床・就寝ルーティン"
    if {"Kitchen","DiningRoom"} <= rs:  return "食事準備・食事行動"
    if {"Kitchen","LivingRoom"} <= rs:  return "調理後リビング滞在"
    if {"Bathroom","Kitchen"} <= rs:    return "朝の身支度"
    if {"Bedroom","Kitchen"} <= rs:     return "就寝前・起床直後"
    if {"Bedroom","LivingRoom"} <= rs:  return "就寝前リビング→寝室"
    if {"Bedroom","Office"} <= rs:      return "在宅作業"
    if {"OutsideDoor"} <= rs:           return "外出・帰宅"
    if {"LaundryRoom"} <= rs:           return "洗濯行動"
    if {"WorkArea"} <= rs:              return "作業場利用"
    if len(rooms)==1:                   return f"{rooms[0]}の継続的利用"
    return "複合居住行動"

def res_label(sh):
    return {0.25:"15分", 0.5:"30分", 1.0:"1時間"}[sh]

def win_label(Wh):
    return {1:"1時間以内", 2:"2時間以内", 3:"3時間以内",
            4:"4時間以内", 6:"6時間以内"}.get(Wh, f"{Wh}h以内")

def dur_h(s, e, sh): return (e - s) * sh

def format_pat(house, pat, sh, Wh):
    rooms = items_to_rooms(house, pat["items"])
    ivs = pat["intervals"]
    if not ivs:
        return f"  **{' + '.join(rooms)}** — 区間なし\n"
    durs = [dur_h(s, e, sh) for s,e in ivs]
    return (
        f"  **{' + '.join(rooms)}**（{win_label(Wh)}で共起）\n"
        f"    - 推定行動: {infer_behaviour(rooms)}\n"
        f"    - 密集区間数: {pat['n_intervals']}  "
        f"平均持続: {sum(durs)/len(durs):.1f}h  最大: {max(durs):.1f}h\n"
        f"    - 期間: {idx_to_date(house, ivs[0][0], sh):%Y-%m-%d} "
        f"〜 {idx_to_date(house, ivs[-1][1], sh):%Y-%m-%d}\n"
    )


def main():
    lines = ["# CASAS Fine-Grain Round-2 (Higher θ)\n",
             f"生成日時: {datetime.now():%Y-%m-%d %H:%M}\n\n---\n"]
    summary = []

    for house in ["hh113", "mv001"]:
        lines.append(f"\n## {house}\n\n")
        for sh, Wh, theta, ml in PARAM_GRID[house]:
            label = f"{res_label(sh)} W={Wh}h θ={theta}"
            print(f"  {house} {label} ...", flush=True)
            pats = run_experiment(house, sh, Wh, theta, ml)
            n = len(pats)
            lines.append(f"### {label}  →  **{n}パターン**\n\n")
            if not pats:
                lines.append("結果なし\n\n---\n\n")
                summary.append((house, sh, Wh, theta, 0, "–"))
                continue
            cnt = Counter(p["size"] for p in pats)
            lines.append("サイズ別: " + ", ".join(f"k={k}:{v}" for k,v in sorted(cnt.items())) + "\n\n")
            top = sorted(pats, key=lambda p:(p["n_intervals"],p["size"]), reverse=True)[:8]
            for i, p in enumerate(top, 1):
                lines.append(f"{i}. {format_pat(house, p, sh, Wh)}\n")
            pairs = [p for p in pats if p["size"]==2]
            bp = max(pairs, key=lambda p:p["n_intervals"]) if pairs else None
            bp_str = f"{' + '.join(items_to_rooms(house, bp['items']))} ({bp['n_intervals']}区間)" if bp else "–"
            lines.append(f"**最頻ペア**: {bp_str}\n\n---\n\n")
            summary.append((house, sh, Wh, theta, n, bp_str))

    lines.append("\n## サマリー\n\n")
    lines.append("| データ | 解像度 | W | θ | パターン数 | 最頻ペア |\n")
    lines.append("|--------|--------|---|---|-----------|----------|\n")
    for house, sh, Wh, th, n, bp in sorted(summary, key=lambda r:(r[0], abs(r[4]-20))):
        lines.append(f"| {house} | {res_label(sh)} | {Wh}h | {th} | {n} | {bp} |\n")

    OUT_MD.write_text("".join(lines), encoding="utf-8")
    print(f"\n完了: {OUT_MD}")

    print("\n=== パターン数が15-30のもの ===")
    for house, sh, Wh, th, n, bp in summary:
        if 10 <= n <= 35:
            print(f"  {house} | {res_label(sh)} W={Wh}h θ={th} → {n}パターン  最頻ペア: {bp}")

if __name__ == "__main__":
    main()
