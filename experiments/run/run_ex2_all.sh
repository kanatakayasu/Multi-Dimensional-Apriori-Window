#!/bin/bash
# EX-2 スケーラビリティ実験: ビルド → 実行 → 結果反映 の一括ラッパー
#
# 使い方:
#   cd <repo_root>
#   bash experiments/run_ex2_all.sh [--dry-run]
#
# --dry-run: 実験は実行するが LaTeX は更新しない（stdout に表示）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN_FLAG=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN_FLAG="--dry-run"
    echo "[dry-run モード]"
fi

echo "============================================================"
echo "EX-2: ビルド → 実行 → 結果反映"
echo "============================================================"

# --- Step 1: Rust ビルド ---
echo ""
echo "--- Step 1: Rust binary ビルド ---"
cd "$REPO_ROOT/apriori_window_md"
cargo build --release --bin md_pipeline
echo "ビルド完了: $(ls -la target/release/md_pipeline | awk '{print $5, $6, $7, $8, $9}')"
cd "$REPO_ROOT"

# --- Step 2: 実験実行 ---
echo ""
echo "--- Step 2: EX-2 実験実行 ---"
python3 experiments/run_ex2_scalability_v4.py

# --- Step 3: 結果反映 ---
echo ""
echo "--- Step 3: 結果 → 論文反映 ---"
python3 experiments/fill_ex2_paper.py $DRY_RUN_FLAG

# --- Step 4: LaTeX コンパイル確認 ---
if [[ -z "$DRY_RUN_FLAG" ]]; then
    echo ""
    echo "--- Step 4: LaTeX コンパイル確認 ---"
    cd "$REPO_ROOT/paper/DSAA2026"
    xelatex -interaction=nonstopmode main.tex 2>&1 | tail -3
    echo ""
    echo "完了。PDF を確認してください: paper/DSAA2026/main.pdf"
else
    echo ""
    echo "[dry-run] LaTeX コンパイルはスキップしました。"
fi
