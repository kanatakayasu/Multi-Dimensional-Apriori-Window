#!/usr/bin/env python3
"""
CASAS Smart Home Dataset Preprocessor
--------------------------------------
Input : labeled_data/labeled/<house>.csv
        Format: date,time,sensor,message[,activity_label]
Output: <house>_<window>h.txt  -- transaction file (space-sep integer IDs per line)
        <house>_<window>h_meta.json -- sensor ID mapping + stats

Each transaction = set of sensor IDs that fired ON within a time window.
Empty windows are included as empty lines (required by Apriori-Window).

Usage:
    python3 preprocess_casas.py [--house hh113] [--window-hours 1] [--min-events 1]
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta


def load_events(path: str):
    """Load ON events from a CASAS CSV file."""
    events = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 4:
                continue
            date_str, time_str, sensor, message = parts[0], parts[1], parts[2], parts[3]
            if message.strip() != "ON":
                continue
            try:
                ts = datetime.strptime(f"{date_str} {time_str[:8]}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            events.append((ts, sensor))
    return events


def events_to_transactions(events, window_hours: float = 1.0, min_events: int = 1):
    """
    Group ON-events into fixed-size time windows.
    Returns list of frozensets (one per window, in chronological order).
    Empty windows are included as empty sets.
    """
    if not events:
        return [], datetime.min, datetime.min

    start_ts = events[0][0].replace(minute=0, second=0, microsecond=0)
    end_ts   = events[-1][0]

    window_delta = timedelta(hours=window_hours)
    buckets = defaultdict(set)

    for ts, sensor in events:
        slot = int((ts - start_ts).total_seconds() / window_delta.total_seconds())
        buckets[slot].add(sensor)

    total_slots = int((end_ts - start_ts).total_seconds() / window_delta.total_seconds()) + 1
    transactions = []
    for i in range(total_slots):
        s = buckets.get(i, set())
        if len(s) >= min_events:
            transactions.append(frozenset(s))
        else:
            transactions.append(frozenset())  # empty transaction

    return transactions, start_ts, start_ts + total_slots * window_delta


def build_sensor_mapping(transactions):
    """Assign integer IDs to sensor names (1-indexed, sorted)."""
    sensors = sorted({s for t in transactions for s in t})
    mapping = {s: i + 1 for i, s in enumerate(sensors)}
    return mapping


def write_transactions(transactions, sensor_map, out_path):
    """Write transaction file: each line = space-sep integer IDs (or empty)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        for t in transactions:
            ids = sorted(sensor_map[s] for s in t)
            f.write(" ".join(map(str, ids)) + "\n")


def write_meta(meta, out_path):
    with open(out_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--house", default="hh113",
                        help="House ID (e.g. hh113, mv001)")
    parser.add_argument("--window-hours", type=float, default=1.0,
                        help="Time window size in hours, e.g. 0.5 for 30min (default: 1)")
    parser.add_argument("--min-events", type=int, default=1,
                        help="Min sensor fires to keep a window non-empty (default: 1)")
    parser.add_argument(
        "--data-dir",
        default=os.path.join(os.path.dirname(__file__), "labeled_data", "labeled"),
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.dirname(__file__),
    )
    args = parser.parse_args()

    csv_path = os.path.join(args.data_dir, f"{args.house}.csv")
    if not os.path.exists(csv_path):
        # fallback: .txt
        csv_path = csv_path.replace(".csv", ".txt")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Not found: {csv_path}")

    print(f"Loading {csv_path} ...")
    events = load_events(csv_path)
    print(f"  ON events: {len(events)}")

    transactions, t_start, t_end = events_to_transactions(
        events, args.window_hours, args.min_events
    )
    sensor_map = build_sensor_mapping(transactions)

    out_name = f"{args.house}_{args.window_hours}h"
    out_txt  = os.path.join(args.out_dir, f"{out_name}.txt")
    out_meta = os.path.join(args.out_dir, f"{out_name}_meta.json")

    write_transactions(transactions, sensor_map, out_txt)

    non_empty = sum(1 for t in transactions if t)
    meta = {
        "house": args.house,
        "window_hours": args.window_hours,
        "min_events": args.min_events,
        "source_csv": csv_path,
        "date_range": {
            "start": str(t_start),
            "end": str(t_end),
        },
        "total_transactions": len(transactions),
        "non_empty_transactions": non_empty,
        "empty_transactions": len(transactions) - non_empty,
        "unique_sensors": len(sensor_map),
        "sensor_id_map": sensor_map,
    }
    write_meta(meta, out_meta)

    print(f"  Transactions : {len(transactions)} total, {non_empty} non-empty")
    print(f"  Unique sensors: {len(sensor_map)}")
    print(f"  Sensor map: {sensor_map}")
    print(f"  Output: {out_txt}")
    print(f"  Meta  : {out_meta}")


if __name__ == "__main__":
    main()
