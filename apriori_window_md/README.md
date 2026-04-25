# apriori_window_md

時間軸を 1 本、空間軸を任意個もつ d 次元グリッド上で Apriori-Window を実行する Rust クレートです。

現在の実装は **dense cell 集合ではなく、空間開始ベクトルごとの時間区間列** を返します。

```text
spatial_start -> [(t_start, t_end), ...]
```

したがって、多次元化しても本質は

- 空間開始ベクトルを 1 つ固定する
- その空間窓へ入る出現を時刻の多重集合へ潰す
- 重複時刻を許す 1D Apriori-Window を解く

という構造です。

## 入口

- `find_dense_itemsets_3d`
- `find_dense_itemsets_nd`

`find_dense_itemsets_3d` は `find_dense_itemsets_nd` の 3 次元ラッパです。

## 主要な型

- `Md3DParams`
- `MdNDParams`
- `Txn3D`
- `TxnND`
- `DenseRegion`
- `DenseRegionND`

`DenseRegion` / `DenseRegionND` は、もう dense cell のリストではありません。

```rust
pub struct DenseRegion {
    pub spatial_start: Vec<usize>,
    pub intervals: Vec<(usize, usize)>,
}
```

3D では `spatial_start.len() == 2`、一般の d 次元では `len() == d - 1` です。

## 窓の意味

`window_bins[0] = Wt`、`window_bins[1..] = spatial windows` です。  
離散ビン上では

```text
[s_0, s_0 + W_0 - 1] × ... × [s_{d-1}, s_{d-1} + W_{d-1} - 1]
```

として扱います。これは半開区間表現と同値です。

## アルゴリズム

### 1. 固定空間開始ベクトルごとに 1D へ潰す

空間開始ベクトル `s_sp = (s_1, ..., s_{d-1})` を固定すると、その空間窓に入る出現は

```text
L_P(s_sp) = sorted multiset of time bins
```

になります。  
同じ時刻に複数セル、あるいは複数トランザクションがあれば、同じ時刻が重複して入ります。

### 2. t 軸は duplicate-aware 1D interval solver

`L_P(s_sp)` に対して、`new_apriori_window` の

- `compute_dense_intervals_multiset`
- `compute_dense_intervals_with_candidates_multiset`

を適用します。

つまり多次元版の中心ロジックは

```text
1D の dense interval 計算 + 空間開始ベクトルでの外側ループ
```

です。

### 3. Apriori 枝刈り

候補パターン `P` に対しては、各 singleton item の

```text
spatial_start -> dense intervals
```

を同じ `spatial_start` ごとに交差し、候補時間区間だけを exact に再評価します。

## フラグの意味

- `use_t_stride = false`
  時間方向を素朴走査して、stride 実装と同じ結果になることを比較できます。
- `use_apriori_prune = false`
  singleton 区間交差による候補区間制限を無効化します。
- `use_prefix_sum`, `use_binsearch`
  旧 dense-cell 実装との互換のために残していますが、現在の interval-based 実装では使いません。

## テスト

```bash
cd apriori_window_md
cargo test
```

現在の Rust テストは 25 件です。

- grid / prefix sum / connected component の既存テスト
- ND interval 出力の naive 一致
- 3D wrapper と ND 実装の一致
- `use_t_stride` の有無による一致
- planted pair / 空入力 / 閾値未満ケース

## ドキュメント

- [MD Explainer](./doc/apriori_window_md_explainer.html)
- [Implementation Log](./doc/impl_log.md)
