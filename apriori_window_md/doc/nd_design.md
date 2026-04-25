# 多次元 Apriori-Window 設計

## 1. 目的

1 次元 / 2 次元で確立した「時間軸だけストライドし、空間軸は 1 ステップずつ扱う」方針を、そのまま d 次元へ一般化する。

ここで

- 第 0 軸は時間 `t`
- 第 1 軸以降は空間
- 窓は半開区間

とする。

## 2. support 定義

パターン `P` の出現集合を

```text
occ(P) ⊆ Z^d
```

とし、開始点 `s = (s_0, ..., s_{d-1})` に対して

```text
S_P(s) =
|{ c ∈ occ(P) | s_k ≤ c_k < s_k + W_k for all k }|
```

を support とする。

密集開始点集合は

```text
Lθ(P) = { s | S_P(s) ≥ θ }
```

である。

## 3. `k = 1` の一般化

### 3.1 固定空間開始ベクトルで 1D に還元

空間開始ベクトル

```text
s_sp = (s_1, ..., s_{d-1})
```

を固定すると、空間窓に入る出現は時刻の多重集合へ潰せる。

```text
L_i(s_sp) = sorted multiset of t
```

したがって `k = 1` の問題は、各 `s_sp` ごとに

```text
count(l_t) = |{ τ ∈ L_i(s_sp) | l_t ≤ τ < l_t + W_t }|
```

を評価する 1D 問題になる。

### 3.2 `t` 軸ストライド

`L = L_i(s_sp)` が空でなければ、`|L| < θ` は即スキップ。

そうでなければ

```text
l_t = L[θ - 1] - W_t + 1
```

から開始する。

各反復で

```text
lo = lower_bound(L, l_t)
hi = lower_bound(L, l_t + W_t)
count = hi - lo
```

を計算する。

- Case A: `count < θ`

```text
if hi == |L|: break
next_outside = L[hi]
l_t = max(l_t + 1, next_outside - W_t + 1)
```

- Case BC: `count ≥ θ`

```text
surplus = count - θ
dense_end = L[lo + surplus]
emit all starts in [l_t, dense_end]
l_t = dense_end + 1
```

2D / dD では `L` が重複時刻を持つので、Case BC は 1 点ジャンプではなく dense block 一括出力になる。

## 4. `k ≥ 2` の一般化

### 4.1 Apriori 候補生成

通常の Apriori と同様に `k-1` 頻出パターンから `k` 候補を作る。

### 4.2 dense cell 交差による候補セル制限

```text
Lθ(P) ⊆ ⋂_{Q ⊂ P, |Q|=|P|-1} Lθ(Q)
```

なので、`P` の候補セルは全 `(k-1)` 部分集合の dense cell 交差でよい。

### 4.3 exact support 評価

候補セルごとに exact support を再計算する。

実装は 2 通り持つ。

- `cell_time_map + binary search`
- `GridND + PrefixSumND`

前者が普段の主経路、後者は比較用・アブレーション用。

## 5. 連結成分

dense cell は各次元 `±1` の 2d 近傍で連結成分化する。

これにより、dense start の集合を region として返せる。

## 6. この設計で保たれるもの

- `k = 1` は空間窓固定ごとに 1D 厳密問題へ還元される
- `k ≥ 2` は Apriori 枝刈りで探索セル数を大きく削減できる
- 2D の議論がそのまま dD へ持ち上がる
