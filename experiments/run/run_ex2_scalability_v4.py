#!/usr/bin/env python3
"""
EX-2 スケーラビリティ実験 v4（ストライド効果を反映する設定）

Part A: N-スケーラビリティ（4×4 グリッド）
  W=(25,5), θ=15, |I|=20, p_item=0.10
  T ∈ {100, 1000, 10000, 100000}
  s ∈ {10, 100, 1000, 10000}

Part B: θ 感度分析（固定 N=10^6）
  W=(25,5), T=10000, s=100
  θ ∈ {3, 6, 9, 12, 15, 18}

使い方:
  cd <repo_root>
  cd apriori_window_md && cargo build --release --bin md_pipeline && cd ..
  python3 experiments/run_ex2_scalability_v4.py
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BIN = REPO_ROOT / "apriori_window_md" / "target" / "release" / "md_pipeline"
OUT_DIR = SCRIPT_DIR / "results" / "ex2_v4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 共通パラメータ
# ---------------------------------------------------------------------------
SEED = 42
N_ITEMS = 20
P_ITEM = 0.10
N_DIMS = 2
MAX_LENGTH = 3
WINDOW = "25,5"
W0, W1 = 25, 5

CHUNK_SIZE = 1_000_000
RUN_TIMEOUT = 6 * 3600  # 6 時間

# ---------------------------------------------------------------------------
# Part A パラメータ
# ---------------------------------------------------------------------------
PART_A_THRESHOLD = 15
T_LIST = [100, 1_000, 10_000, 100_000]
S_LIST = [10, 100, 1_000, 10_000]

# ---------------------------------------------------------------------------
# Part B パラメータ
# ---------------------------------------------------------------------------
PART_B_T = 10_000
PART_B_S = 100
PART_B_THRESHOLDS = [3, 6, 9, 12, 15, 18]


# ---------------------------------------------------------------------------
# データ生成（全セル充填 Bernoulli）
# ---------------------------------------------------------------------------

def gen_full_grid(t_max, s_max, seed, out_path):
    rng = np.random.default_rng(seed)
    grid_vol = t_max * s_max

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# t\tx1\titems...\n")
        for chunk_start in range(0, grid_vol, CHUNK_SIZE):
            chunk_end = min(chunk_start + CHUNK_SIZE, grid_vol)
            n = chunk_end - chunk_start

            masks = rng.random((n, N_ITEMS)) < P_ITEM
            empty = ~masks.any(axis=1)
            masks[empty, 0] = True

            flat = np.arange(chunk_start, chunk_end)
            coords = np.array(np.unravel_index(flat, (t_max, s_max))).T

            lines = []
            for i in range(n):
                t_val, x_val = int(coords[i, 0]), int(coords[i, 1])
                items = ",".join(
                    str(j + 1) for j in range(N_ITEMS) if masks[i, j]
                )
                lines.append(f"{t_val}\t{x_val}\t{items}")
            f.write("\n".join(lines))
            f.write("\n")
    return grid_vol


# ---------------------------------------------------------------------------
# md_pipeline 実行
# ---------------------------------------------------------------------------

def run_once(tsv_path, threshold, timeout=RUN_TIMEOUT):
    cmd = [
        str(BIN), "run",
        "--input", str(tsv_path),
        "--n-dims", str(N_DIMS),
        "--window", WINDOW,
        "--threshold", str(threshold),
        "--max-length", str(MAX_LENGTH),
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "md_pipeline failed")
    elapsed = time.perf_counter() - t0
    n_patterns = sum(
        1 for line in proc.stdout.splitlines()
        if line and not line.startswith("#") and len(line.split("\t")) >= 4
    )
    return {"elapsed_s": round(elapsed, 4), "n_patterns": n_patterns}


# ---------------------------------------------------------------------------
# 1 設定を実行
# ---------------------------------------------------------------------------

def run_config(t_max, s_max, threshold, label):
    n_txn = t_max * s_max
    print(f"\n--- {label}  N={n_txn:>12,} ---", flush=True)

    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        t_gen = time.perf_counter()
        gen_full_grid(t_max, s_max, SEED, tmp_path)
        gen_elapsed = time.perf_counter() - t_gen
        print(f"    gen: {n_txn:,} txn, {gen_elapsed:.1f}s", flush=True)

        res = run_once(tmp_path, threshold)
        print(
            f"  => {res['elapsed_s']:.3f}s, {res['n_patterns']} patterns",
            flush=True,
        )
        return {
            "t_max": t_max,
            "s_max": s_max,
            "threshold": threshold,
            "n_txn": n_txn,
            "gen_s": round(gen_elapsed, 2),
            "run_s": res["elapsed_s"],
            "n_patterns": res["n_patterns"],
        }
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT ({RUN_TIMEOUT}s)", flush=True)
        return {
            "t_max": t_max, "s_max": s_max, "threshold": threshold,
            "n_txn": n_txn, "gen_s": -1, "run_s": -1,
            "n_patterns": -1, "note": "TIMEOUT",
        }
    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return {
            "t_max": t_max, "s_max": s_max, "threshold": threshold,
            "n_txn": n_txn, "gen_s": -1, "run_s": -1,
            "n_patterns": -1, "note": str(e),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    if not BIN.exists():
        sys.exit(
            f"Error: binary not found: {BIN}\n"
            "Run: cd apriori_window_md && cargo build --release --bin md_pipeline"
        )

    print("=" * 70, flush=True)
    print(f"EX-2 v4: W={WINDOW}, |I|={N_ITEMS}, p={P_ITEM}", flush=True)
    print(f"  Part A: θ={PART_A_THRESHOLD}, {len(T_LIST)}×{len(S_LIST)} grid", flush=True)
    print(f"  Part B: T={PART_B_T}, s={PART_B_S}, θ∈{PART_B_THRESHOLDS}", flush=True)
    print("=" * 70, flush=True)

    # --- Part A ---
    print("\n" + "=" * 70, flush=True)
    print("Part A: N-スケーラビリティ (4×4 grid, θ=15)", flush=True)
    print("=" * 70, flush=True)

    part_a = []
    for t_max in T_LIST:
        for s_max in S_LIST:
            label = f"T={t_max:>7,} s={s_max:>6,}"
            r = run_config(t_max, s_max, PART_A_THRESHOLD, label)
            part_a.append(r)

    # --- Part B ---
    print("\n" + "=" * 70, flush=True)
    print(f"Part B: θ 感度分析 (T={PART_B_T}, s={PART_B_S}, N={PART_B_T*PART_B_S:,})", flush=True)
    print("=" * 70, flush=True)

    # データは一度だけ生成して再利用
    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    t_gen = time.perf_counter()
    gen_full_grid(PART_B_T, PART_B_S, SEED, tmp_path)
    gen_elapsed = time.perf_counter() - t_gen
    print(f"    gen: {PART_B_T*PART_B_S:,} txn, {gen_elapsed:.1f}s", flush=True)

    part_b = []
    for theta in PART_B_THRESHOLDS:
        label = f"θ={theta:>2}"
        print(f"\n--- {label} ---", flush=True)
        try:
            res = run_once(tmp_path, theta)
            print(f"  => {res['elapsed_s']:.3f}s, {res['n_patterns']} patterns", flush=True)
            part_b.append({
                "t_max": PART_B_T, "s_max": PART_B_S,
                "threshold": theta,
                "n_txn": PART_B_T * PART_B_S,
                "run_s": res["elapsed_s"],
                "n_patterns": res["n_patterns"],
            })
        except Exception as e:
            print(f"    ERROR: {e}", flush=True)
            part_b.append({
                "t_max": PART_B_T, "s_max": PART_B_S,
                "threshold": theta,
                "n_txn": PART_B_T * PART_B_S,
                "run_s": -1, "n_patterns": -1, "note": str(e),
            })

    tmp_path.unlink(missing_ok=True)

    # --- 保存 ---
    all_results = {"part_a": part_a, "part_b": part_b}
    out_file = OUT_DIR / "ex2_v4_results.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n結果保存: {out_file}", flush=True)

    # --- サマリ ---
    print("\n" + "=" * 70, flush=True)
    print("Part A サマリ (run seconds)", flush=True)
    print("=" * 70, flush=True)
    header = f"{'T':>10} |" + "".join(f" s={s:>6,} |" for s in S_LIST)
    print(header, flush=True)
    print("-" * len(header), flush=True)
    idx = 0
    for t_max in T_LIST:
        row = f"{t_max:>10,} |"
        for _ in S_LIST:
            r = part_a[idx]
            if r["run_s"] < 0:
                row += f" {'TO/ERR':>8} |"
            else:
                row += f" {r['run_s']:>8.3f} |"
            idx += 1
        print(row, flush=True)

    print("\n" + "=" * 70, flush=True)
    print("Part B サマリ (θ vs run seconds)", flush=True)
    print("=" * 70, flush=True)
    for r in part_b:
        t = r["run_s"]
        p = r["n_patterns"]
        ts = f"{t:.3f}s" if t > 0 else "ERR"
        print(f"  θ={r['threshold']:>2}  {ts:>10}  {p} patterns", flush=True)


if __name__ == "__main__":
    main()
