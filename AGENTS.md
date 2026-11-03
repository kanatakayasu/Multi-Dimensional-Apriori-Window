# AGENTS.md — apriori_window

This file defines agent roles for AI-assisted development of the apriori_window project.
Compatible with Claude Code, Cursor, Copilot, and other AI coding assistants.

## Roles

### Architect
- System design and algorithm planning
- Task decomposition into modules
- Design decision documentation (docs/decisions/)
- Ensures Phase1/Phase2 design constraints are maintained

### Researcher
- Literature review and baseline evaluation
- Maintains `baselines/methods/*.md` and `baselines/research/`
- Documents comparative method properties and limitations
- Identifies gaps in `benchmarks/` definitions

### Coder
- Implements features following Python → Rust workflow
- Python prototype in `apriori_window_suite/python/`
- Rust port in `apriori_window_suite/src/`
- Must not break test baselines (see CLAUDE.md §7)
- Uses `/impl-feature` skill for structured implementation

### Experimenter
- Runs benchmarks defined in `benchmarks/suites/`
- Uses configs in `experiments/configs/`
- Records results in `experiments/registry/experiments.csv`
- Outputs to `runs/` (gitignored) and aggregates to `experiments/reports/`
- Uses `/run-experiment` skill

### Writer
- Drafts and revises paper in `paper/`
- Generates figures via `tools/scripts/gen_figs.py`
- Maintains `paper/reproducibility_appendix/`
- Uses `/write-paper` skill

### Consistency Checker (AROB 2027)
Verifies that `paper/AROB2027/` is internally consistent and aligned with the implementation.
Run this agent before any submission or major revision.

**1. Proper noun consistency**
Check every occurrence in `paper/AROB2027/**/*.tex` and `paper/AROB2027/doc/abstract_draft.md`:

| Must use | Must NOT use |
|----------|-------------|
| Streaming Apriori-Window | Apriori-Window 1D, Multi-Dimensional Apriori-Window |
| Scan Stride Skipping | stride skipping, ScanStride, scan-stride |
| Apriori Interval Pruning | interval pruning, AprioriPruning |
| Naive / Stride-only / Pruning-only / Full | other variant names |
| event, event stream | transaction, transactional database |
| Δ (scan interval) | n |
| W (window size), θ (threshold), T (stream length), N (item count) | alternative variable names |

**2. AROB vs DSAA terminology isolation**
- AROB paper must not use DSAA-specific terms (e.g., multi-dimensional, grid, spatial, n-dims)
- arxiv:2604.24122 is cited as a self-citation for the preliminary study (`\cite{takayasu2025arxiv}`)

**3. Implementation alignment**
Cross-check paper algorithm descriptions against `apriori_window_1d/src/`:
- "Full (proposed)" → `find_dense_itemsets` in `lib.rs`
- "Naive" → `find_dense_itemsets_naive`
- "Stride-only" → `find_dense_itemsets_stride_only`
- "Pruning-only" → `find_dense_itemsets_pruning_only`
- Confirm parameter names in function signatures match paper notation (Δ, W, θ, T, N)
- Confirm Scan Stride Skipping description matches the stride-skip logic in `apriori.rs` / `interval.rs`
- Confirm Apriori Interval Pruning description matches the (k−1)-subset interval intersection logic

**4. Experiment number consistency**
Verify claimed numbers against actual benchmark output:
- EX-3 ablation: Full=21.4 ms; Stride Skipping 12.1× vs Naive, Apriori Pruning 7.4×, combined 15.2×
- EX-4 dataset stats: hh113 T=48,901 θ=14 → 26 patterns; mv001 T=139,033 θ=18 → 34 patterns
- EX-1/EX-2: any TODO cells must be filled from actual run output before submission

**5. Abstract format rules**
- Word count: 400–600 English words
- No em dashes (`—` or `---`) in abstract text
- No bare numeric sets like `{1, 6, 24, 96, T}` in abstract
- EN and JA paragraphs correspond paragraph-by-paragraph in content and numbers

## Skills

See `.agents/skills/` for available skills:
- `/impl-feature` — New algorithm feature (Python prototype → Rust)
- `/run-experiment` — Execute benchmark suite
- `/debug-test` — Debug failing tests
- `/write-paper` — Paper writing and revision
- `/git-workflow` — Commit and PR workflow

## Conventions

- Work on `dev_takayasu` branch; PRs target `main`
- Python tests: `pytest apriori_window_suite/python/tests/`
- Rust tests: `cd apriori_window_suite && cargo test`
- 1 commit per intent (prototype / port / test / doc separate)
