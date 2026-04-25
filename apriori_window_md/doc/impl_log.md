# 実装ログ (impl_log.md)

実装完了後に追記する変更履歴。1エントリ = 1コミット意図。

## フォーマット

```
### YYYY-MM-DD — <変更タイトル>
- **対象**: 変更したファイル / モジュール
- **内容**: 何を変更したか（1〜3行）
- **テスト**: 追加・変更したテスト名
- **関連コミット**: <git short hash>
```

---

## ログ

### 2026-03-01 — Phase 1 + Phase 2 統合クレート初期実装
- **対象**: `apriori_window_suite/` クレート全体
- **内容**: Phase 1（バスケット対応 Apriori-window）と Phase 2（イベント時間的関係）を統合
- **テスト**: 54 lib tests + 4 E2E tests
- **関連コミット**: (dev_takayasu ブランチ初期)

### 2026-04-11 — ND 版 `t` 軸ストライドを 2D と同じ dense-block 規則に統一
- **対象**: `src/md_apriori.rs`, `README.md`, `doc/nd_design.md`, `doc/nd_impl_plan.md`, `doc/apriori_window_md_explainer.html`, `doc/t_stride_2d_design.md`
- **内容**: 固定空間窓ごとの時刻多重集合に対して、`count ≥ θ` のとき dense start の連続ブロックを一括出力する実装へ更新
- **内容**: ND の exact 一致テストを追加し、README / explainer / 設計書を新規整備
- **テスト**: 31 passed
- **関連コミット**: working tree

### 2026-04-12 — ND を interval-based 表現へ移行
- **対象**: `src/md_apriori.rs`, `src/bin/md_pipeline.rs`, `Cargo.toml`, `README.md`, `doc/apriori_window_md_explainer.html`
- **内容**: dense cell / connected component 出力をやめ、`spatial_start -> time intervals` の区間表現へ変更
- **内容**: 固定空間開始ベクトルごとに 1D duplicate-aware interval solver を適用する構成へ統一し、3D wrapper も ND 実装へ流す形に整理
- **テスト**: 25 passed
- **関連コミット**: working tree
