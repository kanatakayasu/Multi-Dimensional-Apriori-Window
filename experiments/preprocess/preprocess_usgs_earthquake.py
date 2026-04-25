"""
USGS Earthquake Catalog を md_pipeline 3D/4D-TSV 形式に変換する前処理スクリプト。

入力: dataset/usgs_earthquake/earthquakes.csv
      列: time, latitude, longitude, depth, mag

出力 (3D): experiments/data/usgs_eq_3d_<region>_<suffix>.tsv
出力 (4D): experiments/data/usgs_eq_4d_<region>_<suffix>.tsv
           experiments/data/usgs_eq_{3d|4d}_<region>_<suffix>_meta.json

TSV 形式（3次元）: t\tx\ty\titems
  t = week index (2000-01-01 基準, 0-indexed)
  x = latitude  bin (floor((lat - lat_min) / bin_lat))
  y = longitude bin (floor((lon - lon_min) / bin_lon))
  items = magnitude band IDs (comma separated, 1-indexed)

TSV 形式（4次元）: t\tx\ty\tz\titems
  z = depth bin (floor(depth / bin_depth))

magnitude band (アイテム定義):
  1: M 2.5–3.0
  2: M 3.0–4.0
  3: M 4.0–5.0
  4: M 5.0–6.0
  5: M 6.0+

【軸の尺度】
  t: 順序（週の連番）
  x: 比例（北方向に単調増加する緯度ビン）
  y: 比例（東方向に単調増加する経度ビン）
  z: 比例（深度が大きいほど地下深く → 単調増加の順序尺度）
  items: 名義（マグニチュード帯）

使い方:
  # California 3D（デフォルト）
  python3 preprocess_usgs_earthquake.py

  # California 4D（深度軸追加, 0--40km を 10km ビン）
  python3 preprocess_usgs_earthquake.py --dims 4

  # 日本域 3D
  python3 preprocess_usgs_earthquake.py --region japan

  # カスタム bbox / ビンサイズ
  python3 preprocess_usgs_earthquake.py \\
    --lat-min 24 --lat-max 46 --lon-min 122 --lon-max 146 \\
    --bin-lat 1.0 --bin-lon 1.0 --bin-depth 10.0 --max-depth 40.0
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, date, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "dataset" / "usgs_earthquake" / "earthquakes.csv"
OUT_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_DATE = date(2000, 1, 1)

# マグニチュード帯 (上限は含まない, 最後のバンドは無限大)
MAG_BANDS = [
    (2.5, 3.0, 1),   # M 2.5–3.0
    (3.0, 4.0, 2),   # M 3.0–4.0
    (4.0, 5.0, 3),   # M 4.0–5.0
    (5.0, 6.0, 4),   # M 5.0–6.0
    (6.0, 999, 5),   # M 6.0+
]
MAG_BAND_LABELS = {
    1: "M2.5-3.0", 2: "M3.0-4.0", 3: "M4.0-5.0",
    4: "M5.0-6.0", 5: "M6.0+",
}

# 深度帯 (アイテム定義の代替案: サブダクションゾーン向け)
DEPTH_BANDS = [
    (0,   35,  1),   # 浅発 (地殻内)
    (35,  70,  2),   # 上部マントル
    (70,  150, 3),   # 中深発
    (150, 300, 4),   # 深発
    (300, 700, 5),   # 極深発
]
DEPTH_BAND_LABELS = {
    1: "depth_0-35km", 2: "depth_35-70km", 3: "depth_70-150km",
    4: "depth_150-300km", 5: "depth_300-700km",
}

REGIONS = {
    "california": dict(lat_min=32.0, lat_max=42.0, lon_min=-124.0, lon_max=-114.0),
    "japan":      dict(lat_min=24.0, lat_max=46.0, lon_min=122.0,  lon_max=146.0),
    "alaska":     dict(lat_min=54.0, lat_max=72.0, lon_min=-168.0, lon_max=-140.0),
    "chile":      dict(lat_min=-56.0,lat_max=-17.0,lon_min=-76.0,  lon_max=-65.0),
}

RAW_DEPTH_MAX_VALID = 700.0  # km（生データの妥当性確認用）
DEFAULT_MAX_DEPTH_KM = 40.0  # km（4D 実験で使う深度上限）


def mag_to_band(mag: float) -> int:
    for lo, hi, band_id in MAG_BANDS:
        if lo <= mag < hi:
            return band_id
    return 5  # fallback


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="USGS Earthquake → 3D/4D TSV")
    p.add_argument("--dims", type=int, choices=[3, 4], default=3,
                   help="出力次元数: 3=t×lat×lon, 4=t×lat×lon×depth (デフォルト: 3)")
    p.add_argument("--region", choices=list(REGIONS), default="california",
                   help="プリセット地域 (デフォルト: california)")
    p.add_argument("--lat-min",   type=float)
    p.add_argument("--lat-max",   type=float)
    p.add_argument("--lon-min",   type=float)
    p.add_argument("--lon-max",   type=float)
    p.add_argument("--bin-lat",   type=float, default=0.5,
                   help="緯度ビン幅（度, デフォルト: 0.5）")
    p.add_argument("--bin-lon",   type=float, default=0.5,
                   help="経度ビン幅（度, デフォルト: 0.5）")
    p.add_argument("--bin-depth", type=float, default=10.0,
                   help="深度ビン幅（km, デフォルト: 10）")
    p.add_argument("--max-depth", type=float, default=DEFAULT_MAX_DEPTH_KM,
                   help="4D 出力で保持する最大深度（km, デフォルト: 40）。以上は外れ値として除外")
    p.add_argument("--items", choices=["mag", "depth"], default="mag",
                   help="アイテム定義: mag=マグニチュード帯（デフォルト）, depth=深度帯（3D用サブダクション向け）")
    p.add_argument("--time-bin", type=int, default=7,
                   help="時間ビン幅（日数）。7=週次（デフォルト）, 28=月次")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # bbox 解決
    bbox = dict(REGIONS[args.region])
    if args.lat_min is not None: bbox["lat_min"] = args.lat_min
    if args.lat_max is not None: bbox["lat_max"] = args.lat_max
    if args.lon_min is not None: bbox["lon_min"] = args.lon_min
    if args.lon_max is not None: bbox["lon_max"] = args.lon_max

    lat_min, lat_max = bbox["lat_min"], bbox["lat_max"]
    lon_min, lon_max = bbox["lon_min"], bbox["lon_max"]
    bin_lat, bin_lon, bin_depth = args.bin_lat, args.bin_lon, args.bin_depth
    dims = args.dims
    items_mode = args.items
    time_bin_days = args.time_bin

    n_lat_bins = math.ceil((lat_max - lat_min) / bin_lat)
    n_lon_bins = math.ceil((lon_max - lon_min) / bin_lon)
    max_depth = args.max_depth
    n_dep_bins = math.ceil(max_depth / bin_depth)

    suffix = f"{args.region}_blat{bin_lat:.1f}_blon{bin_lon:.1f}"
    if time_bin_days != 7:
        suffix += f"_t{time_bin_days}d"
    if items_mode != "mag":
        suffix += f"_items{items_mode}"
    if dims == 4:
        suffix += f"_bdep{bin_depth:.0f}"
    dim_tag = f"{dims}d"
    out_tsv  = OUT_DIR / f"usgs_eq_{dim_tag}_{suffix}.tsv"
    out_meta = OUT_DIR / f"usgs_eq_{dim_tag}_{suffix}_meta.json"

    print(f"地域: {args.region}  bbox: lat[{lat_min},{lat_max}] lon[{lon_min},{lon_max}]")
    print(f"ビン: lat={bin_lat}°({n_lat_bins}bins)  lon={bin_lon}°({n_lon_bins}bins)"
          + (f"  depth={bin_depth}km({n_dep_bins}bins, max={max_depth:.0f}km)" if dims == 4 else ""))
    print(f"次元数: {dims}D")

    # --- Step 1: 集約 ---
    print(f"Step 1: {RAW} を読み込み ...")
    if dims == 3:
        cell_items: dict[tuple, set[int]] = defaultdict(set)
    else:
        cell_items = defaultdict(set)
    n_valid = n_skipped = 0
    n_depth_outliers = 0

    with open(RAW) as f:
        for row in csv.DictReader(f):
            try:
                lat   = float(row["latitude"])
                lon   = float(row["longitude"])
                depth = float(row["depth"])
                mag   = float(row["mag"])
                t_str = row["time"].strip()
            except (ValueError, KeyError):
                n_skipped += 1
                continue

            # bbox フィルタ
            if not (lat_min <= lat < lat_max and lon_min <= lon < lon_max):
                n_skipped += 1
                continue
            # 深度異常値除外
            if depth < 0 or depth > RAW_DEPTH_MAX_VALID:
                n_skipped += 1
                continue
            if dims == 4 and depth >= max_depth:
                n_depth_outliers += 1
                continue

            # 時刻解析
            try:
                dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                d  = dt.date()
            except ValueError:
                n_skipped += 1
                continue

            week    = (d - BASE_DATE).days // time_bin_days
            lat_bin = int((lat   - lat_min) / bin_lat)
            lon_bin = int((lon   - lon_min) / bin_lon)
            lat_bin = max(0, min(lat_bin, n_lat_bins - 1))
            lon_bin = max(0, min(lon_bin, n_lon_bins - 1))

            if items_mode == "mag":
                item_id = mag_to_band(mag)
            else:
                # depth を items として使う（3D 用サブダクション向け）
                item_id = next(
                    (bid for lo, hi, bid in DEPTH_BANDS if lo <= depth < hi), 5
                )

            if dims == 3:
                cell_items[(week, lat_bin, lon_bin)].add(item_id)
            else:
                dep_bin = int(depth / bin_depth)
                dep_bin = max(0, min(dep_bin, n_dep_bins - 1))
                cell_items[(week, lat_bin, lon_bin, dep_bin)].add(item_id)

            n_valid += 1

    n_cells = len(cell_items)
    coord_idx = 0  # t は常に先頭
    all_weeks = sorted({k[0] for k in cell_items})
    week_range = (min(all_weeks), max(all_weeks))
    avg_items  = sum(len(v) for v in cell_items.values()) / n_cells if n_cells else 0

    print(f"  有効イベント: {n_valid:,}  スキップ: {n_skipped:,}")
    if dims == 4:
        print(f"  深度外れ値として除外: {n_depth_outliers:,} (depth >= {max_depth:.0f} km)")
    print(f"  グリッドセル数: {n_cells:,}")
    print(f"  週範囲: {week_range[0]} ~ {week_range[1]} ({week_range[1]-week_range[0]+1}週)")
    print(f"  平均 items/cell: {avg_items:.2f}")

    # --- Step 2: TSV 出力 ---
    print(f"Step 2: TSV 出力 → {out_tsv}")
    with open(out_tsv, "w") as f:
        header = "# t\tx\ty\titems..." if dims == 3 else "# t\tx\ty\tz\titems..."
        f.write(header + "\n")
        for key, item_ids in sorted(cell_items.items()):
            coords = "\t".join(map(str, key))
            items_str = ",".join(map(str, sorted(item_ids)))
            f.write(f"{coords}\t{items_str}\n")

    # --- Step 3: メタデータ ---
    meta = {
        "source":        "USGS Earthquake Catalog (ComCat), M2.5+, 2000-2020",
        "region":        args.region,
        "bbox":          bbox,
        "dims":          dims,
        "bin_lat_deg":   bin_lat,
        "bin_lon_deg":   bin_lon,
        "bin_depth_km":  bin_depth if dims == 4 else None,
        "max_depth_km":  max_depth if dims == 4 else None,
        "base_date":     BASE_DATE.isoformat(),
        "n_valid_events":n_valid,
        "n_skipped":     n_skipped,
        "n_depth_outliers": n_depth_outliers if dims == 4 else None,
        "n_cells":       n_cells,
        "n_lat_bins":    n_lat_bins,
        "n_lon_bins":    n_lon_bins,
        "n_dep_bins":    n_dep_bins if dims == 4 else None,
        "week_range":    week_range,
        "n_weeks":       week_range[1] - week_range[0] + 1,
        "avg_items_per_cell": round(avg_items, 2),
        "magnitude_bands": MAG_BAND_LABELS,
        "axes_note": (
            "全軸が順序/比例尺度。"
            "t=時間（週）、x=緯度ビン（北増加）、y=経度ビン（東増加）"
            + ("、z=深度ビン（深い方向に増加）" if dims == 4 else "")
            + "。スライディングウィンドウの近傍が地理的・物理的近傍に対応。"
        ),
    }
    with open(out_meta, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n完了:")
    print(f"  {out_tsv}  ({n_cells:,} 行)")
    print(f"  {out_meta}")
    print(f"\n推奨実験設定 ({dims}D, {args.region}):")
    if dims == 3:
        print(f"  --n-dims 3  --window 13,3,3  --threshold 3  --max-length 2")
        print(f"  グリッドサイズ: {week_range[1]-week_range[0]+1} × {n_lat_bins} × {n_lon_bins}")
    else:
        print(f"  --n-dims 4  --window 13,3,3,2  --threshold 3  --max-length 2")
        print(f"  グリッドサイズ: {week_range[1]-week_range[0]+1} × {n_lat_bins} × {n_lon_bins} × {n_dep_bins}")


if __name__ == "__main__":
    main()
