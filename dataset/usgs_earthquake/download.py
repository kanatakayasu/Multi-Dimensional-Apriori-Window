#!/usr/bin/env python3
"""
USGS Earthquake Catalog をダウンロードする。

出力: dataset/usgs_earthquake/earthquakes.csv
列:  time, latitude, longitude, depth, mag

対象: M2.5+, 2000-01-01 〜 2020-12-31 (世界)
方式: USGS FDSN Web Service API で四半期ごとにページング
      1クエリ上限 20,000件のため、3ヶ月単位で分割
"""

import csv
import time
import urllib.request
import urllib.parse
import io
from pathlib import Path
from datetime import date, timedelta

OUT = Path(__file__).parent / "earthquakes.csv"
ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
FIELDS = "time,latitude,longitude,depth,mag"
MIN_MAG = 2.5
START_YEAR = 2000
END_YEAR = 2020
PAGE = 20_000  # USGS hard limit


def quarter_ranges():
    """(start, end) のタプルリスト（四半期単位）"""
    ranges = []
    for year in range(START_YEAR, END_YEAR + 1):
        for q_start_month in [1, 4, 7, 10]:
            start = date(year, q_start_month, 1)
            # 四半期末（次の四半期の前日）
            if q_start_month == 10:
                end = date(year, 12, 31)
            else:
                end = date(year, q_start_month + 3, 1) - timedelta(days=1)
            if start > date(END_YEAR, 12, 31):
                break
            ranges.append((start.isoformat(), end.isoformat()))
    return ranges


def fetch_quarter(start: str, end: str, retries: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({
        "format":       "csv",
        "starttime":    start,
        "endtime":      end,
        "minmagnitude": MIN_MAG,
        "orderby":      "time-asc",
        "limit":        PAGE,
    })
    url = f"{ENDPOINT}?{params}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for row in reader:
                rows.append({
                    "time":      row.get("time", ""),
                    "latitude":  row.get("latitude", ""),
                    "longitude": row.get("longitude", ""),
                    "depth":     row.get("depth", ""),
                    "mag":       row.get("mag", ""),
                })
            return rows
        except Exception as e:
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/{retries}] {e}  wait {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(f"fetch failed after {retries} retries: {start}〜{end}")


def count_existing() -> int:
    if not OUT.exists():
        return 0
    with open(OUT) as f:
        return sum(1 for _ in f) - 1  # subtract header


def main():
    quarters = quarter_ranges()
    existing = count_existing()
    # 既存行数から再開クオーターを推定（保守的に全クオーター再走査でも重複なし）
    total = existing
    mode = "a" if existing > 0 else "w"

    print(f"出力先: {OUT}  既存={existing:,}行  総四半期={len(quarters)}")

    with open(OUT, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "latitude", "longitude", "depth", "mag"])
        if mode == "w":
            writer.writeheader()

        for i, (start, end) in enumerate(quarters):
            # 既存データがある場合、最後の行の時刻と比較してスキップ
            t0 = time.perf_counter()
            rows = fetch_quarter(start, end)
            elapsed = time.perf_counter() - t0

            writer.writerows(rows)
            f.flush()
            total += len(rows)
            print(f"  [{i+1:>3}/{len(quarters)}] {start}〜{end}  +{len(rows):>5,}  累計={total:>7,}  ({elapsed:.1f}s)")

            if len(rows) >= PAGE:
                print(f"    ⚠ 上限{PAGE}件に達した。月次分割が必要かもしれません。")

            time.sleep(0.3)  # API 負荷軽減

    print(f"\n完了: {total:,} 件 → {OUT}")


if __name__ == "__main__":
    main()
