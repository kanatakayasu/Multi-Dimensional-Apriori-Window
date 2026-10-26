# CLAUDE.md — apriori-window-C

## 0. リポジトリ概要

スライディングウィンドウを用いた密集アイテムセット区間の厳密列挙アルゴリズム群。
2つのクレートと2つの論文トラックで構成される。

| クレート | 説明 | 対応論文 |
|---------|------|---------|
| `apriori_window_1d/` | 1次元（時系列）ストリーミング対応 | AROB 2027 |
| `apriori_window_md/` | 多次元（時空間）バッチ処理 | DSAA 2026 |

`apriori_window_md` は `apriori_window_1d` をライブラリ依存として使用する。

---

## 1. ディレクトリ構成

```
apriori_window_1d/          ← 1D アルゴリズム（AROB 2027 用）
  src/
    lib.rs, apriori.rs, interval.rs, io.rs, util.rs
    main.rs                 ← CLI エントリポイント
    bin/
      streaming_benchmark.rs  ← n-Step Streaming ベンチマーク

apriori_window_md/          ← 多次元アルゴリズム（DSAA 2026 用）
  src/
    lib.rs, grid_nd.rs, md_apriori.rs, util.rs
    bin/
      md_pipeline.rs        ← gen / run サブコマンド

dataset/
  casas/                    ← CASAS スマートホームデータ（AROB 2027）
    preprocess_casas.py, hh113_*.txt, mv001_*.txt, settings_*.json
  chicago_crime/            ← シカゴ犯罪データ（DSAA 2026）
  nyc_311/                  ← NYC 311 データ（DSAA 2026）
  nyc_crime/                ← NYC 犯罪データ（DSAA 2026）
  usgs_earthquake/          ← USGS 地震データ（DSAA 2026）

experiments/                ← DSAA 2026 実験スクリプト・結果
  data/                     ← 前処理済み TSV データ
  figures/                  ← 論文図表・生成スクリプト
  preprocess/               ← 前処理スクリプト
  results/                  ← 実験結果（ex1_v2, ex2_extended, ex3 等）
  run/                      ← 実験実行スクリプト
  third_party/              ← 比較手法（catchcore, dcube, mzoom）

paper/
  AROB2027/                 ← AROB 2027 アブスト・研究計画
    abstract_draft.md, research_plan.md
  DSAA2026/                 ← DSAA 2026 日本語論文 LaTeX
  DSAA2026_eng/             ← DSAA 2026 英語論文 LaTeX
  bibliography/             ← 共有 BibTeX
  research/                 ← 文献調査・ギャップ分析
  reproducibility_appendix/ ← 再現性資料

doc/
  research/                 ← アルゴリズム比較・研究ポジショニング

Presentation/               ← DSAA 2026 発表資料
```

---

## 2. ビルド・テスト

```sh
# 1D クレート
cd apriori_window_1d
cargo build --release
cargo test

# 多次元クレート
cd apriori_window_md
cargo build --release
cargo test

# 1D ストリーミングベンチマーク
cd apriori_window_1d
cargo run --release --bin streaming_benchmark -- \
  ../dataset/casas/hh113_1h.txt 24 10 4

# 多次元パイプライン
cd apriori_window_md
./target/release/md_pipeline run \
  --input ../experiments/data/<input.tsv> \
  --n-dims 3 --window 24,4,4 --threshold 15
```

---

## 3. 論文トラック別メモ

### AROB 2027（1D ストリーミング）

- **アブスト締め切り**: 2026-10-28
- **タイトル**: Streaming Apriori-Window: Mining Dense Patterns from Streaming Data for Autonomous Agent Monitoring
- **実験**:
  - EX-1: n パラメータ感度（スキャン頻度 vs 処理速度）
  - EX-2: アブレーション（Naive / Stride-only / Pruning-only / Full）
  - EX-3: CASAS 実データ適用（hh113, mv001）
- **主要ファイル**: `apriori_window_1d/`, `dataset/casas/`, `paper/AROB2027/`

### DSAA 2026（多次元バッチ）

- **タイトル**: Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions
- **実験**: `experiments/run/` 配下のスクリプトで再現可能
- **主要ファイル**: `apriori_window_md/`, `experiments/`, `paper/DSAA2026_eng/`

---

## 4. 設計原則

- `apriori_window_md` は `apriori_window_1d` をライブラリとして依存する（`path = "../apriori_window_1d"`）
- 両クレートとも `cargo test` が全 pass であること
- 最小差分の原則: 要求された変更のみ行い、関係のないコードには触れない
- APIキー・認証情報をコミットしない

---

## 5. Git ワークフロー

- ブランチ: `main`（安定版）
- 論文別作業は `paper/<paper-id>` ブランチを切る
- コミット粒度: 1コミット1意図
