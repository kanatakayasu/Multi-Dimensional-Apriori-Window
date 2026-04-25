#!/usr/bin/env python3
"""
NYPD Complaint Data Historic をダウンロードする。

出力: dataset/nyc_crime/complaints.csv
列:  cmplnt_fr_dt, ofns_desc, latitude, longitude

対象: 2018-01-01 〜 2022-12-31（5年間、lat/lon あるもの）
方式: NYC Open Data Socrata API でページング（50,000件/ページ）
"""

import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

OUT = Path(__file__).parent / "complaints.csv"
ENDPOINT = "https://data.cityofnewyork.us/resource/qgea-i56i.json"
FIELDS = "cmplnt_fr_dt,ofns_desc,latitude,longitude"
WHERE = (
    "cmplnt_fr_dt between '2018-01-01T00:00:00' and '2022-12-31T23:59:59' "
    "AND latitude IS NOT NULL AND longitude IS NOT NULL"
)
PAGE = 50_000


def fetch_page(offset: int, retries: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({
        "$select": FIELDS,
        "$where":  WHERE,
        "$limit":  PAGE,
        "$offset": offset,
        "$order":  "cmplnt_fr_dt",
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


def count_existing() -> int:
    if not OUT.exists():
        return 0
    with open(OUT) as f:
        return sum(1 for _ in f) - 1


def main():
    existing = count_existing()
    start_offset = (existing // PAGE) * PAGE
    total = start_offset
    mode = "a" if start_offset > 0 else "w"

    if existing > 0:
        print(f"再開: 既存 {existing:,} 行 → offset={start_offset:,} から")

    print(f"出力先: {OUT}")

    with open(OUT, mode, newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["cmplnt_fr_dt", "ofns_desc", "latitude", "longitude"]
        )
        if mode == "w":
            writer.writeheader()

        offset = start_offset
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
