#!/usr/bin/env python3
"""
AROB 2027 experiment runner.
Runs EX-1, EX-2, EX-3 and generates EX-2 scalability figure.

Run from the apriori_window_1d/ directory (where target/release/ lives):
  cd apriori_window_1d
  python3 ../experiments/run/arob_experiments.py
"""

import subprocess
import re
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT        = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
BIN         = os.path.join(ROOT, "apriori_window_1d", "target", "release")
STREAMING   = os.path.join(BIN, "streaming_benchmark")
SCALABILITY = os.path.join(BIN, "scalability")
ABLATION    = os.path.join(BIN, "ablation")
FIG_DIR     = os.path.join(ROOT, "paper", "AROB2027", "jpn", "fig")

os.makedirs(FIG_DIR, exist_ok=True)

# ── helpers ───────────────────────────────────────────────────────────────────

def run_stdout(cmd):
    """Return stdout as stripped string."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip()


def run_timed(cmd):
    """Run with /usr/bin/time -l, return (stdout, peak_mem_mb)."""
    full = ["/usr/bin/time", "-l"] + cmd
    r = subprocess.run(full, capture_output=True, text=True)
    m = re.search(r"(\d+)\s+maximum resident set size", r.stderr)
    mem_mb = int(m.group(1)) / 1_048_576 if m else 0.0
    return r.stdout.strip(), mem_mb


# ── EX-1 ─────────────────────────────────────────────────────────────────────

def run_ex1():
    """EX-1: h vs processing speed (synthetic, T=10000, N=20, W=24, theta=10)."""
    print("=== EX-1: h vs processing speed ===")
    out = run_stdout([STREAMING, "--synth", "10000", "20", "24", "10"])
    print(out)
    results = []
    for line in out.splitlines():
        parts = line.split()
        # header/separator lines
        if not parts or parts[0].startswith("-") or not parts[0][0].isdigit():
            continue
        h_val = int(parts[0].replace(",", ""))
        t_ms  = float(parts[1])
        speedup_str = parts[2].rstrip("x")
        speedup = float(speedup_str)
        results.append((h_val, t_ms, speedup))
    return results


# ── EX-2 ─────────────────────────────────────────────────────────────────────

T_VALS  = [1_000, 10_000, 100_000, 1_000_000, 10_000_000]
N_VALS  = [12, 24, 48, 96]
W_VALS  = [120, 240, 480, 960]
BASE_T, BASE_N, BASE_W, BASE_THETA = 100_000, 24, 120, 10


def run_ex2_point(T, N, W, theta):
    out, mem_mb = run_timed([SCALABILITY, str(T), str(N), str(W), str(theta)])
    time_ms = float(out.strip())
    return time_ms, mem_mb


def run_ex2():
    """EX-2: scalability (vary T, N, W independently, h=T)."""
    print("\n=== EX-2: Scalability ===")
    results = {"T": [], "N": [], "W": []}

    print(f"vary T  (N={BASE_N}, W={BASE_W}, θ={BASE_THETA})")
    for T in T_VALS:
        t_ms, mem = run_ex2_point(T, BASE_N, BASE_W, BASE_THETA)
        results["T"].append((T, t_ms, mem))
        print(f"  T={T:>10,}: {t_ms:9.1f} ms  {mem:6.1f} MB")

    print(f"vary N  (T={BASE_T}, W={BASE_W}, θ={BASE_THETA})")
    for N in N_VALS:
        t_ms, mem = run_ex2_point(BASE_T, N, BASE_W, BASE_THETA)
        results["N"].append((N, t_ms, mem))
        print(f"  N={N:>3}: {t_ms:9.1f} ms  {mem:6.1f} MB")

    print(f"vary W  (T={BASE_T}, N={BASE_N}, θ={BASE_THETA})")
    for W in W_VALS:
        t_ms, mem = run_ex2_point(BASE_T, BASE_N, W, BASE_THETA)
        results["W"].append((W, t_ms, mem))
        print(f"  W={W:>4}: {t_ms:9.1f} ms  {mem:6.1f} MB")

    return results


def plot_ex2(results):
    """Generate 2×3 scalability figure."""
    fig, axes = plt.subplots(2, 3, figsize=(8.0, 4.4))
    plt.rcParams.update({"font.size": 8})

    params   = ["T", "N", "W"]
    xlabels  = ["Stream length $T$", "Items $N$", "Window size $W$"]
    colors_t = "steelblue"
    colors_m = "darkorange"

    for col, (param, xlabel) in enumerate(zip(params, xlabels)):
        data   = results[param]
        xs     = [d[0] for d in data]
        t_vals = [d[1] for d in data]
        m_vals = [d[2] for d in data]

        ax_t = axes[0][col]
        ax_m = axes[1][col]

        ax_t.plot(xs, t_vals, "o-", color=colors_t, linewidth=1.5, markersize=4)
        ax_m.plot(xs, m_vals, "s-", color=colors_m, linewidth=1.5, markersize=4)

        for ax in (ax_t, ax_m):
            ax.set_xlabel(xlabel, fontsize=7)
            if param == "T":
                ax.set_xscale("log")
            ax.grid(True, alpha=0.3, linewidth=0.5)
            ax.tick_params(labelsize=7)

        ax_t.set_ylabel("Time (ms)", fontsize=7)
        ax_m.set_ylabel("Peak RSS (MB)", fontsize=7)

    axes[0][1].set_title("EX-2: Scalability", fontsize=9, pad=6)

    plt.tight_layout(pad=0.8, h_pad=1.0, w_pad=0.8)
    out_path = os.path.join(FIG_DIR, "ex2_scalability.pdf")
    plt.savefig(out_path, bbox_inches="tight")
    print(f"\nFigure → {out_path}")
    return out_path


# ── EX-3 ─────────────────────────────────────────────────────────────────────

def run_ex3():
    """EX-3: ablation (T=100K, N=24, W=120, theta=50, h=T)."""
    print("\n=== EX-3: Ablation ===")
    out = run_stdout([ABLATION, "--synth", "100000", "48", "120", "50", "1000"])
    print(out)

    results = {}
    for line in out.splitlines():
        for name, key in [
            ("Naive", "Naive"),
            ("Stride-only", "Stride-only"),
            ("Pruning-only", "Pruning-only"),
            ("Full (proposed)", "Full"),
        ]:
            if line.startswith(name):
                nums = re.findall(r"[\d.]+", line)
                results[key] = float(nums[0])
    return results


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.chdir(os.path.join(ROOT, "apriori_window_1d"))

    ex1 = run_ex1()
    ex2 = run_ex2()
    plot_ex2(ex2)
    ex3 = run_ex3()

    # ── print paper update summary ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PAPER UPDATE SUMMARY")
    print("=" * 60)

    print("\n[EX-1 table]")
    base_ms = ex1[0][1] if ex1 else 1.0
    for h, t_ms, speedup in ex1:
        print(f"  h={h:<8} | {t_ms:>8.1f} ms | {speedup:>6.1f}x")

    print("\n[EX-2 data]")
    for axis in ("T", "N", "W"):
        base = ex2[axis][0][1]
        print(f"  vary {axis}:")
        for val, t_ms, mem_mb in ex2[axis]:
            ratio = t_ms / base
            print(f"    {val:>12,} | {t_ms:>8.1f} ms | x{ratio:>5.2f} | {mem_mb:>6.1f} MB")

    print("\n[EX-3 table]")
    naive_ms = ex3.get("Naive", 1.0)
    for name in ("Naive", "Stride-only", "Pruning-only", "Full"):
        t_ms = ex3.get(name, float("nan"))
        speedup = naive_ms / t_ms
        print(f"  {name:<18} | {t_ms:>8.1f} ms | {speedup:>5.1f}x")
