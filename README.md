# Apriori-Window

Exact mining of dense itemset intervals using a sliding window — in one dimension (time series) and multiple dimensions (spatio-temporal).

---

## Papers

### DSAA 2026 — Multi-Dimensional Apriori-Window

> "Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions"

Given spatio-temporal transaction data, finds every itemset and every spatio-temporal window in which it occurs densely — simultaneously and exactly.

**Crate**: `apriori_window_md/`

```bash
cd apriori_window_md && cargo build --release
./target/release/md_pipeline run \
  --input ../experiments/data/<input.tsv> \
  --n-dims 3 --window 24,4,4 --threshold 15
```

Reproducing experiments:

```bash
python3 experiments/run/run_ex1_v2.py        # EX-1: exactness verification
python3 experiments/run/run_ex2_extended.py  # EX-2: scalability
python3 experiments/figures/gen_fig_ex1_heatmap.py
```

---

### AROB 2027 — Streaming Apriori-Window

> "Streaming Apriori-Window: Mining Dense Patterns from Streaming Data for Autonomous Agent Monitoring"

Extends the 1D algorithm to event streams with a tunable scan frequency parameter *n*: scan every *n* events for confirmed dense interval output, with full batch processing as a special case (*n* = *T*).

**Crate**: `apriori_window_1d/`

```bash
cd apriori_window_1d && cargo build --release
cargo run --release --bin streaming_benchmark -- \
  ../dataset/casas/hh113_1h.txt 24 10 4
```

---

## Repository layout

```
apriori_window_1d/   1D streaming algorithm (AROB 2027)
apriori_window_md/   Multi-dimensional batch algorithm (DSAA 2026)
dataset/             Datasets (casas/, chicago_crime/, nyc_311/, ...)
experiments/         DSAA 2026 experiment scripts and results
paper/               LaTeX sources and drafts (AROB2027/, DSAA2026/)
doc/                 Research notes and algorithm comparisons
Presentation/        DSAA 2026 slides
```

---

## Build

Requires [Rust](https://rustup.rs/) stable 1.75+.

```bash
# 1D
cd apriori_window_1d && cargo build --release

# Multi-dimensional
cd apriori_window_md && cargo build --release
```

---

## License

MIT
