"""
NYPD Complaint Data を md_pipeline 3D-TSV 形式に変換する前処理スクリプト。

入力: dataset/nyc_crime/complaints.csv
      列: cmplnt_fr_dt, ofns_desc, latitude, longitude

出力: experiments/data/nyc_crime_3d_<suffix>.tsv
      experiments/data/nyc_crime_3d_<suffix>_meta.json

TSV 形式（3次元）: t\tx\ty\titems_comma_separated
  t = sequential week index (2018-01-01 基準, 0-indexed)
  x = latitude  bin (floor((lat - NYC_LAT_MIN) / BIN_SIZE))
  y = longitude bin (floor((lon - NYC_LON_MIN) / BIN_SIZE))
  items = offense type IDs (comma separated, 1-indexed)

各行は (week, lat_bin, lon_bin) セルごとの集約トランザクション。

【軸の尺度】
  t: 順序（週の連番）
  x: 比例（北方向に単調増加する緯度ビン）
  y: 比例（東方向に単調増加する経度ビン）

使い方:
  python3 preprocess_nyc_crime.py [--bin-size 0.01]
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW = REPO_ROOT / "dataset" / "nyc_crime" / "complaints.csv"
OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_DATE = date(2018, 1, 1)
DEFAULT_BIN_SIZE = 0.01  # degrees (~1km at NYC's latitude)

# NYC city bounding box
NYC_LAT_MIN = 40.49
NYC_LAT_MAX = 40.92
NYC_LON_MIN = -74.27
NYC_LON_MAX = -73.69


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NYPD Complaint → 3D TSV")
    p.add_argument("--bin-size", type=float, default=DEFAULT_BIN_SIZE,
                   help=f"緯度・経度ビン幅（度）。デフォルト: {DEFAULT_BIN_SIZE}")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bin_size = args.bin_size

    n_lat_bins = math.ceil((NYC_LAT_MAX - NYC_LAT_MIN) / bin_size)
    n_lon_bins = math.ceil((NYC_LON_MAX - NYC_LON_MIN) / bin_size)

    suffix = f"bs{bin_size:.3f}".replace(".", "p")
    out_tsv  = OUT_DIR / f"nyc_crime_3d_{suffix}.tsv"
    out_meta = OUT_DIR / f"nyc_crime_3d_{suffix}_meta.json"

    print(f"グリッド: lat {NYC_LAT_MIN}~{NYC_LAT_MAX} ({n_lat_bins}bins) "
          f"× lon {NYC_LON_MIN}~{NYC_LON_MAX} ({n_lon_bins}bins)")

    # --- Step 1: アイテム（offense type）のインデックス収集 ---
    print(f"Step 1: {RAW} をスキャンしてアイテム種別を収集 ...")
    type_set: set[str] = set()
    n_raw = 0

    with open(RAW) as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (ValueError, KeyError):
                continue
            if not (NYC_LAT_MIN <= lat <= NYC_LAT_MAX and NYC_LON_MIN <= lon <= NYC_LON_MAX):
                continue
            ot = row.get("ofns_desc", "").strip()
            if ot:
                type_set.add(ot)
            n_raw += 1

    types_sorted = sorted(type_set)
    type_to_id = {t: i + 1 for i, t in enumerate(types_sorted)}
    print(f"  有効イベント数（フィルタ後）: {n_raw:,}")
    print(f"  offense 種別数: {len(types_sorted)}")

    # --- Step 2: (week, lat_bin, lon_bin) → offense type set に集約 ---
    print("Step 2: グリッドセルへ集約 ...")
    cell_items: dict[tuple[int, int, int], set[int]] = defaultdict(set)
    n_skipped = 0

    with open(RAW) as f:
        for row in csv.DictReader(f):
            date_str = row.get("cmplnt_fr_dt", "").strip()
            ot = row.get("ofns_desc", "").strip()
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (ValueError, KeyError):
                n_skipped += 1
                continue

            if not (NYC_LAT_MIN <= lat <= NYC_LAT_MAX and NYC_LON_MIN <= lon <= NYC_LON_MAX):
                n_skipped += 1
                continue
            if not ot or ot not in type_to_id:
                n_skipped += 1
                continue

            try:
                dt = datetime.fromisoformat(date_str.replace("T", " ").split(".")[0])
            except ValueError:
                n_skipped += 1
                continue

            week    = (dt.date() - BASE_DATE).days // 7
            lat_bin = int((lat - NYC_LAT_MIN) / bin_size)
            lon_bin = int((lon - NYC_LON_MIN) / bin_size)
            lat_bin = max(0, min(lat_bin, n_lat_bins - 1))
            lon_bin = max(0, min(lon_bin, n_lon_bins - 1))

            cell_items[(week, lat_bin, lon_bin)].add(type_to_id[ot])

    n_cells    = len(cell_items)
    weeks      = sorted({w for w, _, _ in cell_items})
    week_range = (min(weeks), max(weeks))
    avg_items  = sum(len(v) for v in cell_items.values()) / n_cells

    print(f"  スキップ: {n_skipped:,}")
    print(f"  グリッドセル数: {n_cells:,}")
    print(f"  週範囲: {week_range[0]} ~ {week_range[1]} ({week_range[1]-week_range[0]+1} 週)")
    print(f"  平均 items/cell: {avg_items:.2f}")

    # --- Step 3: TSV 出力 ---
    print(f"Step 3: TSV 出力 → {out_tsv}")
    with open(out_tsv, "w") as f:
        f.write("# t\tx\ty\titems...\n")
        for (week, lat_bin, lon_bin), item_ids in sorted(cell_items.items()):
            items_str = ",".join(map(str, sorted(item_ids)))
            f.write(f"{week}\t{lat_bin}\t{lon_bin}\t{items_str}\n")

    # --- Step 4: メタデータ ---
    meta = {
        "source":         "NYC Open Data, NYPD Complaint Data Historic 2018-2022",
        "bin_size_deg":   bin_size,
        "base_date":      BASE_DATE.isoformat(),
        "bbox":           {"lat_min": NYC_LAT_MIN, "lat_max": NYC_LAT_MAX,
                           "lon_min": NYC_LON_MIN, "lon_max": NYC_LON_MAX},
        "n_raw_events":   n_raw,
        "n_skipped":      n_skipped,
        "n_cells":        n_cells,
        "n_weeks":        week_range[1] - week_range[0] + 1,
        "week_range":     week_range,
        "n_lat_bins":     n_lat_bins,
        "n_lon_bins":     n_lon_bins,
        "n_offense_types":len(types_sorted),
        "offense_types":  {t: i for t, i in type_to_id.items()},
        "grid_dims":      f"week({week_range[1]-week_range[0]+1}) x lat_bin({n_lat_bins}) x lon_bin({n_lon_bins})",
        "axes_note":      "全軸が順序/比例尺度。スライディングウィンドウの地理的近傍が成立。",
    }
    with open(out_meta, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n完了:")
    print(f"  {out_tsv}  ({n_cells:,} 行)")
    print(f"  {out_meta}")
    print(f"\n推奨実験設定 (bin_size={bin_size:.3f}°):")
    print(f"  --n-dims 3  --window 4,3,3  --threshold 5  --max-length 2")
    print(f"  グリッドサイズ: {week_range[1]-week_range[0]+1} × {n_lat_bins} × {n_lon_bins}")


if __name__ == "__main__":
    main()
