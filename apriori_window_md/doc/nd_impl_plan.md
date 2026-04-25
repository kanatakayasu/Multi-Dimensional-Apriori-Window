# 多次元 Apriori-Window 実装計画

この文書は、d 次元版をどの順序で実装・検証するかを固定するための計画メモである。現行実装はこの計画に沿って反映済み。

## 1. 実装方針

1. `k = 1` は「固定空間窓ごとの時刻多重集合」に還元する
2. `t` 軸だけストライドし、空間軸は 1 ステップずつ扱う
3. `k ≥ 2` は Apriori 候補生成 + dense cell 交差で候補を絞る
4. support 再計算は `cell_time_map + 二分探索` を主経路とする
5. naive / prefix sum を比較用に残す

## 2. 変更対象

- `src/md_apriori.rs`
- `src/grid_nd.rs`
- `README.md`
- `doc/nd_design.md`
- `doc/apriori_window_md_explainer.html`
- `doc/impl_log.md`

## 3. ステップ

### Step 1. `k = 1` の `t` 軸ストライドを 2D と同じ意味論に揃える

- 初期位置を `θ` 番目の出現から決める
- `count < θ` は `next_outside - W_t + 1`
- `count ≥ θ` は dense block 一括出力

### Step 2. 一般化版の正しさをテストで固定する

- 重複時刻ありケース
- 小入力全探索
- naive ND との exact 一致
- 既存 3D 実装との一致

### Step 3. ドキュメントを追加する

- crate README
- explainer
- 設計メモ

## 4. 完了条件

- `cargo test` が全通
- README / explainer が現行コードと整合
- 2D で確立した dense block 規則が ND 側でも明文化されている
