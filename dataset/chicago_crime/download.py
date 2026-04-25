#!/usr/bin/env python3
"""
Chicago Crime データを Chicago Data Portal (Socrata) からダウンロードする。

出力: dataset/chicago_crime/crime_latlon.csv
列:  date, primary_type, latitude, longitude

対象: 2018-01-01 〜 2022-12-31（5年間、約120万件）
方式: Socrata API でページング（50,000件/ページ）
"""

import csv
import sys
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path

OUT = Path(__file__).parent / "crime_latlon.csv"
ENDPOINT = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
FIELDS = "date,primary_type,latitude,longitude"
WHERE = "year between 2018 and 2022 AND latitude IS NOT NULL AND longitude IS NOT NULL"
PAGE = 50_000


def fetch_page(offset: int, retries: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({
        "$select": FIELDS,
        "$where":  WHERE,
        "$limit":  PAGE,
        "$offset": offset,
        "$order":  "date",
    })
    url = f"{ENDPOINT}?{params}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{retries}] {e}  wait {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(f"fetch failed after {retries} retries at offset={offset}")


def count_existing_rows(path: Path) -> int:
    """既存ファイルの行数（ヘッダ除く）を返す。"""
    if not path.exists():
        return 0
    with open(path) as f:
        return sum(1 for line in f) - 1  # subtract header


def main():
    # 既存ファイルから再開
    existing = count_existing_rows(OUT)
    start_offset = (existing // PAGE) * PAGE  # PAGE の倍数に切り捨て
    if existing > 0:
        print(f"再開: 既存 {existing:,} 行 → offset={start_offset:,} から")
        # 中途半端なページ分を末尾から切り捨てて再取得
        if existing > start_offset:
            lines = OUT.read_text().splitlines()
            OUT.write_text("\n".join(lines[: start_offset + 1]) + "\n")  # header + start_offset rows

    print(f"出力先: {OUT}")
    total = start_offset
    offset = start_offset
    mode = "a" if start_offset > 0 else "w"

    with open(OUT, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "primary_type", "latitude", "longitude"])
        if mode == "w":
            writer.writeheader()

        while True:
            t0 = time.perf_counter()
            rows = fetch_page(offset)
            elapsed = time.perf_counter() - t0

            if not rows:
                break

            writer.writerows(rows)
            f.flush()
            total += len(rows)
            print(f"  offset={offset:>8,}  +{len(rows):>6,}  累計={total:>8,}  ({elapsed:.1f}s)")

            if len(rows) < PAGE:
                break
            offset += PAGE

    print(f"\n完了: {total:,} 件 → {OUT}")


if __name__ == "__main__":
    main()
