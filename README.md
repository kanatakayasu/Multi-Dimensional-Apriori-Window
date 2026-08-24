# Multi-Dimensional Apriori-Window

Exact mining of dense itemset regions over arbitrary $d$-dimensional grids.

Given spatio-temporal transaction data, this tool finds every itemset $P$ and every spatio-temporal window in which $P$ occurs densely — simultaneously and exactly.

> **Paper:** "Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions" (DSAA 2026, submitted)

---

## What it does

Standard frequent itemset mining (Apriori, FP-Growth) reports globally frequent patterns and discards locality.
This tool answers the finer question:

> *Which itemsets are dense, and **when and where**?*

**Output** — for each dense pattern $P$, a list of spatio-temporal windows $(s_1, \ldots, s_{d-1}, t_{\rm start}, t_{\rm end})$ in which $P$ exceeds the density threshold.

---

## Repository layout

```
apriori_window_md/   main implementation (d-dimensional, Rust)
apriori_window_1d/   1-D interval solver used as a library by apriori_window_md
experiments/         scripts to reproduce paper experiments
paper/DSAA2026_eng/  LaTeX source of the paper
```

---

## Build

Requires [Rust](https://rustup.rs/) (stable, 1.75+).

```bash
cd apriori_window_md
cargo build --release
```

The binary is at `apriori_window_md/target/release/md_pipeline`.

---

## Quick start

### 1. Generate synthetic data

```bash
cd apriori_window_md
./target/release/md_pipeline gen \
  --out data/sample.tsv \
  --n-dims 3 \
  --n-txn 50000 \
  --p-item 0.15 \
  --n-items 20 \
  --space-max 50.0 \
  --t-max 200.0 \
  --seed 42
```

### 2. Run the algorithm

```bash
./target/release/md_pipeline run \
  --input data/sample.tsv \
  --n-dims 3 \
  --window 24,4,4 \
  --threshold 15
```

---

## Input format

Tab-separated values (TSV), one transaction per line:

```
<t>   <x1>  <x2>  ...  <item1> <item2> ...
```

- Columns 0 … d−1: continuous coordinates (time first, then spatial axes)
- Remaining columns: item IDs (integers ≥ 1, variable number per row)

Coordinates are discretized internally using `--bin-size` (default 1.0 per axis) or per-axis flags (`--dt`, `--dx`, …).

---

## Key parameters

| Flag | Description | Default |
|------|-------------|---------|
| `--window N,...` | Window size in bins for each axis (d values, comma-separated) | `5,3,3` |
| `--threshold N` | Minimum occurrence count within a window | `3` |
| `--bin-size F,...` | Bin width for each axis (d values, comma-separated) | `1.0` per axis |
| `--n-dims N` | Number of dimensions (time + spatial) | `3` |
| `--max-length N` | Maximum pattern size | unlimited |

The window along axis $k$ covers $W_k$ discrete bins.
A pattern is **dense** at a window if it occurs at least $\theta$ times within it.

---

## Algorithm overview

Three techniques realize exact multi-dimensional dense region enumeration:

1. **1-D reduction per spatial start point** — for each fixed spatial origin $(s_1,\ldots,s_{d-1})$, occurrences falling inside the spatial window are collapsed into a temporal multiset.
2. **Duplicate-aware $t$-axis stride** — the 1-D Apriori-Window interval solver is extended to handle duplicate timestamps arising from multi-dimensional data, processing contiguous dense blocks in bulk.
3. **Apriori pruning via $(k-1)$-subset interval map intersection** — candidate temporal intervals for a size-$k$ pattern are restricted to the intersection of dense intervals of all $(k-1)$-subsets, enabling efficient exact enumeration without redundant scan.

---

## Reproducing paper experiments

```bash
# EX-1: exactness verification on synthetic data (4 region shapes)
python3 experiments/run/run_ex1_v2.py

# EX-2: scalability (T, S, d, |I| axes)
python3 experiments/run/run_ex2_extended.py

# Regenerate figures
python3 experiments/figures/gen_fig_ex1_heatmap.py
python3 experiments/run/plot_ex2_extended.py
```

---

## Citation

```bibtex
@inproceedings{takayasu2026mdaprioriwindow,
  title     = {Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions},
  author    = {Takayasu, Kanata and Takahashi, Taihei and Suga, Satoshi and Kurihara, Satoshi},
  booktitle = {Proceedings of the 2026 IEEE International Conference on Data Science and Advanced Analytics (DSAA)},
  year      = {2026}
}
```

---

## License

MIT
