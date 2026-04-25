"""
Chicago Crime データを md_pipeline 3D-TSV 形式に変換する前処理スクリプト。

入力: dataset/chicago_crime/crime_latlon.csv
      列: date, primary_type, latitude, longitude

出力: experiments/data/chicago_crime_3d.tsv
      experiments/data/chicago_crime_3d_meta.json

TSV 形式（3次元）: t\tx\ty\titems_comma_separated
  t = sequential week index (2018-01-01 基準, 0-indexed)
  x = latitude bin  index  (floor((lat - lat_min) / BIN_SIZE))
  y = longitude bin index  (floor((lon - lon_min) / BIN_SIZE))
  items = crime type IDs (comma separated, 1-indexed)

各行は (week, lat_bin, lon_bin) セルごとの集約トランザクション。
同一セルに複数の crime type が存在する場合は和集合をとる。

【重要】軸はすべて順序/比例尺度:
  t: 時間の経過（連続整数）
  x: 緯度ビン（北方向に単調増加）
  y: 経度ビン（東方向に単調増加）
  → スライディングウィンドウ「近傍 = 地理的近傍」が成立する。

使い方:
  python3 preprocess_chicago_crime.py [--bin-size 0.02]
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW = REPO_ROOT / "dataset" / "chicago_crime" / "crime_latlon.csv"
OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_DATE = date(2018, 1, 1)
DEFAULT_BIN_SIZE = 0.02  # degrees (~2km at Chicago's latitude)

# Chicago city bounding box（外れ値除去用）
CHICAGO_LAT_MIN = 41.60
CHICAGO_LAT_MAX = 42.05
CHICAGO_LON_MIN = -87.95
CHICAGO_LON_MAX = -87.50


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Chicago Crime → 3D TSV")
    p.add_argument("--bin-size", type=float, default=DEFAULT_BIN_SIZE,
                   help=f"緯度・経度ビン幅（度）。デフォルト: {DEFAULT_BIN_SIZE}")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bin_size = args.bin_size

    suffix = f"bs{bin_size:.3f}".replace(".", "p")
    out_tsv  = OUT_DIR / f"chicago_crime_3d_{suffix}.tsv"
    out_meta = OUT_DIR / f"chicago_crime_3d_{suffix}_meta.json"

    # --- Step 1: 全行スキャンして lat/lon の実範囲を確定 ---
    print(f"Step 1: {RAW} を全件スキャンして lat/lon 範囲を確定 ...")
    lat_vals, lon_vals = [], []
    type_set: set[str] = set()
    n_raw = 0

    with open(RAW) as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (ValueError, KeyError):
                continue
            # Chicago バウンディングボックス外を除外
            if not (CHICAGO_LAT_MIN <= lat <= CHICAGO_LAT_MAX and
                    CHICAGO_LON_MIN <= lon <= CHICAGO_LON_MAX):
                continue
            lat_vals.append(lat)
            lon_vals.append(lon)
            type_set.add(row["primary_type"].strip())
            n_raw += 1

    lat_min = math.floor(min(lat_vals) / bin_size) * bin_size
    lon_min = math.floor(min(lon_vals) / bin_size) * bin_size
    lat_max = math.ceil(max(lat_vals)  / bin_size) * bin_size
    lon_max = math.ceil(max(lon_vals)  / bin_size) * bin_size
    n_lat_bins = round((lat_max - lat_min) / bin_size)
    n_lon_bins = round((lon_max - lon_min) / bin_size)

    print(f"  lat: {lat_min:.4f} ~ {lat_max:.4f}  ({n_lat_bins} bins)")
    print(f"  lon: {lon_min:.4f} ~ {lon_max:.4f}  ({n_lon_bins} bins)")
    print(f"  犯罪種別: {len(type_set)} 種")

    # --- Step 2: インデックス割り当て ---
    types_sorted = sorted(type_set)
    type_to_id = {t: i + 1 for i, t in enumerate(types_sorted)}  # 1-indexed

    # --- Step 3: (week, lat_bin, lon_bin) → crime type set に集約 ---
    print("Step 3: グリッドセルへ集約 ...")
    cell_items: dict[tuple[int, int, int], set[int]] = defaultdict(set)
    n_skipped = 0

    with open(RAW) as f:
        for row in csv.DictReader(f):
            date_str = row.get("date", "").strip()
            pt = row.get("primary_type", "").strip()
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (ValueError, KeyError):
                n_skipped += 1
                continue
            # Chicago バウンディングボックス外を除外
            if not (CHICAGO_LAT_MIN <= lat <= CHICAGO_LAT_MAX and
                    CHICAGO_LON_MIN <= lon <= CHICAGO_LON_MAX):
                n_skipped += 1
                continue
            try:
                dt = datetime.fromisoformat(date_str.replace("T", " ").split(".")[0])
            except ValueError:
                n_skipped += 1
                continue

            week    = (dt.date() - BASE_DATE).days // 7
            lat_bin = int((lat - lat_min) / bin_size)
            lon_bin = int((lon - lon_min) / bin_size)

            # 範囲外クリップ（浮動小数点誤差対策）
            lat_bin = max(0, min(lat_bin, n_lat_bins - 1))
            lon_bin = max(0, min(lon_bin, n_lon_bins - 1))

            cell_items[(week, lat_bin, lon_bin)].add(type_to_id[pt])

    n_cells  = len(cell_items)
    weeks    = sorted({w for w, _, _ in cell_items})
    week_range = (min(weeks), max(weeks))
    avg_items  = sum(len(v) for v in cell_items.values()) / n_cells

    print(f"  有効イベント: {n_raw - n_skipped:,}  スキップ: {n_skipped}")
    print(f"  グリッドセル数: {n_cells:,}")
    print(f"  週範囲: {week_range[0]} ~ {week_range[1]} ({week_range[1] - week_range[0] + 1} 週)")
    print(f"  平均 items/cell: {avg_items:.2f}")

    # --- Step 4: TSV 出力 ---
    print(f"Step 4: TSV 出力 → {out_tsv}")
    with open(out_tsv, "w") as f:
        f.write("# t\tx\ty\titems...\n")
        for (week, lat_bin, lon_bin), item_ids in sorted(cell_items.items()):
            items_str = ",".join(map(str, sorted(item_ids)))
            f.write(f"{week}\t{lat_bin}\t{lon_bin}\t{items_str}\n")

    # --- Step 5: メタデータ出力 ---
    meta = {
        "source":       "Chicago Data Portal, Crimes 2018-2022",
        "bin_size_deg": bin_size,
        "base_date":    BASE_DATE.isoformat(),
        "n_raw_events": n_raw,
        "n_skipped":    n_skipped,
        "n_cells":      n_cells,
        "n_weeks":      week_range[1] - week_range[0] + 1,
        "week_range":   week_range,
        "n_lat_bins":   n_lat_bins,
        "n_lon_bins":   n_lon_bins,
        "lat_min":      lat_min,
        "lon_min":      lon_min,
        "lat_max":      lat_max,
        "lon_max":      lon_max,
        "n_crime_types": len(type_set),
        "crime_types":  {t: i for t, i in type_to_id.items()},
        "grid_dims":    f"week({week_range[1]-week_range[0]+1}) x lat_bin({n_lat_bins}) x lon_bin({n_lon_bins})",
        "axes_note":    "全軸が順序/比例尺度。スライディングウィンドウの地理的近傍が成立。",
    }
    with open(out_meta, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n完了:")
    print(f"  {out_tsv}  ({n_cells:,} 行)")
    print(f"  {out_meta}")
    print(f"\n推奨実験設定 (bin_size={bin_size:.3f}°):")
    print(f"  --n-dims 3  --window 4,3,3  --threshold 3  --max-length 2")
    print(f"  グリッドサイズ: {week_range[1]-week_range[0]+1} × {n_lat_bins} × {n_lon_bins}")


if __name__ == "__main__":
    main()
