# 2D `t` 軸ストライド設計メモ

現在の `apriori_window_2d` 実装に対応する短い設計メモ。

## 1. セマンティクス

- 窓は半開区間 ` [s_t, s_t + Wt) × [s_x, s_x + Wx) `
- `s_x` を固定すると、問題は時刻の多重集合 `L_P(s_x)` 上の 1D 問題へ還元できる
- 多重集合なので、同じ `t` が複数回現れる

## 2. `k = 1` のストライド

### 初期化

```text
if |L| < θ: skip
l_t = max(0, L[θ - 1] - Wt + 1)
```

### Case A

```text
count < θ
next_outside = L[hi]
l_t = max(l_t + 1, next_outside - Wt + 1)
```

### Case BC

```text
count ≥ θ
surplus = count - θ
dense_end = L[lo + surplus]
emit every dense start in [l_t, dense_end]
l_t = dense_end + 1
```

ここで重要なのは、2D では dense interval の右端だけが欲しいのではなく、
各 `s_x` に対する dense start 自体を全列挙したい点である。
そのため `+1` で 1 点ジャンプするのではなく、dense block をまとめて吐く必要がある。

## 3. `k ≥ 2`

- Apriori 候補生成
- 部分集合 dense cell の交差
- exact support の再計算

で処理する。

詳細は以下を参照。

- `../README.md`
- `./apriori_window_2d_explainer.html`
