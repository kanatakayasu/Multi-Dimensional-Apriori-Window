#!/usr/bin/env python3
"""
EX-2 Extended: 4-parameter scalability (runtime + peak memory)

(a) T-scalability : vary T in {100,1K,10K,100K,1M}, fix S=100, d=2, |I|=20
(b) S-scalability : vary S in {10,100,1K,10K,100K}, fix T=1000, d=2, |I|=20
(c) d-scalability : vary d in {2,3,4}, fix N~=10^5, |I|=20
(d) |I|-scalability: vary |I| in {10,20,40,60,80,100}, fix T=1000, S=100, d=2

Metrics per setting: runtime (s) + peak RSS memory (MB) via /usr/bin/time -l
Base params: W=(24,4,...), theta=15, p_item=0.10, seed=42, max-length=3
"""

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
BIN = REPO_ROOT / "apriori_window_md" / "target" / "release" / "md_pipeline"
OUT_DIR = REPO_ROOT / "experiments" / "results" / "ex2_extended"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Common params (consistent with existing EX-2 v4)
# ---------------------------------------------------------------------------
SEED = 42
P_ITEM = 0.10
W_T = 24
W_SP = 4        # window per spatial dim
THETA = 15
MAX_LENGTH = 3
TIMEOUT = 600   # seconds

CHUNK_SIZE = 1_000_000

# ---------------------------------------------------------------------------
# Data generation (arbitrary d dimensions)
# dims = [t_max, s1_max, s2_max, ...]  (length = d)
# ---------------------------------------------------------------------------

def gen_nd_grid(dims, n_items, p_item, seed, out_path):
    rng = np.random.default_rng(seed)
    d = len(dims)
    total = 1
    for dim in dims:
        total *= dim

    with open(out_path, "w", encoding="utf-8") as f:
        for chunk_start in range(0, total, CHUNK_SIZE):
            chunk_end = min(chunk_start + CHUNK_SIZE, total)
            n = chunk_end - chunk_start

            masks = rng.random((n, n_items)) < p_item
            empty = ~masks.any(axis=1)
            masks[empty, 0] = True

            flat = np.arange(chunk_start, chunk_end)
            coords = np.array(np.unravel_index(flat, tuple(dims))).T  # (n, d)

            lines = []
            for i in range(n):
                coord_str = "\t".join(str(int(coords[i, k])) for k in range(d))
                items = ",".join(str(j + 1) for j in range(n_items) if masks[i, j])
                lines.append(f"{coord_str}\t{items}")
            f.write("\n".join(lines) + "\n")

    return total


# ---------------------------------------------------------------------------
# Run md_pipeline, measure runtime + peak RSS (/usr/bin/time -l on macOS)
# ---------------------------------------------------------------------------

def run_with_memory(dims, n_items, timeout=TIMEOUT):
    """
    Generate data in a temp file, run md_pipeline wrapped with /usr/bin/time -l,
    return dict with elapsed_s, peak_rss_mb, n_patterns.
    dims = [t_max, s1_max, ...], n_items = |I|
    """
    d = len(dims)
    window_str = ",".join([str(W_T)] + [str(W_SP)] * (d - 1))

    with tempfile.NamedTemporaryFile(suffix=".tsv", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # --- Data generation ---
        t_gen = time.perf_counter()
        total_txn = gen_nd_grid(dims, n_items, P_ITEM, SEED, tmp_path)
        gen_s = time.perf_counter() - t_gen

        # --- Run with /usr/bin/time -l ---
        cmd = [
            "/usr/bin/time", "-l",
            str(BIN), "run",
            "--input", str(tmp_path),
            "--n-dims", str(d),
            "--window", window_str,
            "--threshold", str(THETA),
            "--max-length", str(MAX_LENGTH),
        ]

        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.perf_counter() - t0

        if proc.returncode != 0 and "maximum resident set size" not in proc.stderr:
            raise RuntimeError(proc.stderr.strip() or "md_pipeline failed")

        # Parse peak RSS from stderr (macOS: bytes)
        peak_rss_mb = None
        for line in proc.stderr.splitlines():
            if "maximum resident set size" in line:
                m = re.search(r"(\d+)", line)
                if m:
                    peak_rss_mb = int(m.group(1)) / (1024 * 1024)
                break

        n_patterns = sum(
            1 for line in proc.stdout.splitlines()
            if line and not line.startswith("#") and len(line.split("\t")) >= 4
        )

        return {
            "elapsed_s": round(elapsed, 3),
            "peak_rss_mb": round(peak_rss_mb, 1) if peak_rss_mb else None,
            "n_patterns": n_patterns,
            "n_txn": total_txn,
            "gen_s": round(gen_s, 2),
        }

    except subprocess.TimeoutExpired:
        return {"elapsed_s": None, "peak_rss_mb": None, "n_patterns": None,
                "n_txn": None, "note": "TIMEOUT"}
    except Exception as e:
        return {"elapsed_s": None, "peak_rss_mb": None, "n_patterns": None,
                "n_txn": None, "note": str(e)}
    finally:
        tmp_path.unlink(missing_ok=True)


def print_result(label, r):
    t = f"{r['elapsed_s']:.3f}s" if r.get("elapsed_s") is not None else r.get("note", "ERR")
    m = f"{r['peak_rss_mb']:.1f}MB" if r.get("peak_rss_mb") is not None else "?"
    p = r.get("n_patterns", "?")
    n = r.get("n_txn")
    n_str = f"{n:>10,}" if n is not None else f"{'?':>10}"
    print(f"  {label:40s}  N={n_str}  {t:>10}  {m:>10}  {p} patterns", flush=True)


# ---------------------------------------------------------------------------
# (a) T-scalability
# ---------------------------------------------------------------------------

def run_exp_a():
    print("\n" + "=" * 70)
    print("(a) T-scalability  fix S=100, d=2, |I|=20")
    print("=" * 70)
    T_LIST = [100, 1_000, 10_000, 100_000, 1_000_000]
    S_FIX = 100
    results = []
    for t in T_LIST:
        label = f"T={t:>9,}"
        r = run_with_memory([t, S_FIX], n_items=20)
        r.update({"T": t, "S": S_FIX, "d": 2, "n_items": 20})
        print_result(label, r)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# (b) S-scalability
# ---------------------------------------------------------------------------

def run_exp_b():
    print("\n" + "=" * 70)
    print("(b) S-scalability  fix T=1000, d=2, |I|=20")
    print("=" * 70)
    S_LIST = [10, 100, 1_000, 10_000]  # 100K は N=10^8 でタイムアウトのため除外
    T_FIX = 1_000
    results = []
    for s in S_LIST:
        label = f"S={s:>9,}"
        r = run_with_memory([T_FIX, s], n_items=20)
        r.update({"T": T_FIX, "S": s, "d": 2, "n_items": 20})
        print_result(label, r)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# (c) d-scalability  (fix N~=10^5)
# ---------------------------------------------------------------------------

def run_exp_c():
    print("\n" + "=" * 70)
    print("(c) d-scalability  fix N~=10^5, |I|=20")
    print("=" * 70)
    # N ~= 10^5 throughout; W_sp = (W_SP+1)^(d-1)
    configs = [
        (2, [1_000, 100]),          # N=100,000  W_sp=5
        (3, [1_000, 10, 10]),       # N=100,000  W_sp=25
        (4, [1_000, 5, 5, 4]),      # N=100,000  W_sp=125
    ]
    results = []
    for d, dims in configs:
        w_sp = (W_SP + 1) ** (d - 1)
        label = f"d={d}  dims={dims}  W_sp={w_sp}"
        r = run_with_memory(dims, n_items=20)
        r.update({"d": d, "dims": dims, "W_sp": w_sp, "n_items": 20})
        print_result(label, r)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# (d) |I|-scalability
# ---------------------------------------------------------------------------

def run_exp_d():
    print("\n" + "=" * 70)
    print("(d) |I|-scalability  fix T=1000, S=100, d=2")
    print("=" * 70)
    I_LIST = [10, 20, 40, 60, 80, 100]
    T_FIX, S_FIX = 1_000, 100
    results = []
    for n_items in I_LIST:
        label = f"|I|={n_items:>3}"
        r = run_with_memory([T_FIX, S_FIX], n_items=n_items)
        r.update({"T": T_FIX, "S": S_FIX, "d": 2, "n_items": n_items})
        print_result(label, r)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not BIN.exists():
        sys.exit(
            f"Error: binary not found: {BIN}\n"
            "Run: cd apriori_window_md && cargo build --release --bin md_pipeline"
        )

    print("=" * 70)
    print(f"EX-2 Extended: W=({W_T},{W_SP},...), theta={THETA}, p={P_ITEM}, seed={SEED}")
    print("=" * 70)

    results = {
        "params": {"W_T": W_T, "W_SP": W_SP, "theta": THETA,
                   "p_item": P_ITEM, "seed": SEED, "max_length": MAX_LENGTH},
        "exp_a": run_exp_a(),
        "exp_b": run_exp_b(),
        "exp_c": run_exp_c(),
        "exp_d": run_exp_d(),
    }

    out_file = OUT_DIR / "results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果保存: {out_file}", flush=True)


if __name__ == "__main__":
    main()
