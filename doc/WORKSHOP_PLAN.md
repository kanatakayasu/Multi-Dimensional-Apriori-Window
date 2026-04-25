# CIKMワークショップ論文 計画

## 概要

DSAA 2026に投稿中のMulti-Dimensional Apriori-Window論文をarXivに掲載し、
それを引用する形でスピードアップ手法のワークショップ論文をCIKM 2026に投稿する。

---

## タイムライン

| 日程 | イベント |
|---|---|
| 2026-05-01 | DSAA 2026 投稿〆切 |
| 2026-07-24 | DSAA 通知 |
| 2026-07月末 | arXivに英語版を投稿（DSAA版とタイトル・アブスト微修正） |
| 2026-07〜09 | スピードアップ手法の実装・実験・論文執筆 |
| 2026-09-23 | CIKMワークショップ論文〆切（推奨） |
| 2026-10-06〜09 | DSAA 開催（New Delhi） |
| 2026-10-09 | CIKMワークショップ採否通知 |
| 2026-11-08 | CIKMワークショップ開催（Rome） |

---

## Dual Submission について

- DSAA論文: 問題定義 + アルゴリズム + 有効性実証
- WS論文: そのアルゴリズムのk>=2ボトルネックの高速化

貢献が異なるため dual submission には該当しない（companion paper）。

### arXivとDSAAの整合性

DSAA CFPのarXivポリシー:
> arXiv papers posted at least one month prior to submission deadline,
> provided that title and abstract differ from the arXiv version.

推奨: DSAA通知（7/24）後にarXiv投稿が最も安全。
CIKM WS〆切（9/23）には十分間に合う。

---

## 現アルゴリズムのボトルネック（区間ベース実装準拠）

```
k=1: 各アイテム i について
  1. 全N件スキャン -> i を含むトランザクション抽出        O(N)
  2. 各出現を W_sp 個の空間開始点へ配布                   O(N_i * W_sp)
  3. 各空間開始点のタイムスタンプリストをソート             O(N~_i log N~_i)
  4. t軸ストライド（二分探索）で密集区間計算               O(S * log |L|) per spatial start

k>=2: 各候補パターン P について
  5. singleton interval map を交差 -> C(P)                 O(I_P)
  6. 全N件を再スキャン -> P を含むトランザクション抽出     <-- ボトルネック1
  7. 各出現を全 W_sp 個の空間開始点へ配布                  <-- ボトルネック2
  8. C(P) に含まれる空間開始点のみで区間計算               O(候補区間内のみ)
```

核心的な無駄: 5でC(P)を絞っているのに、6,7ではそれを活用せず全データ・全空間をスキャンしている。

---

## スピードアップアイデア

### アイデア1: 転置インデックスによるk>=2フルスキャン排除

**問題**: `build_spatial_t_events_for_pattern_nd` が候補パターンごとに全N件をスキャンする。

**提案**: k=1で各アイテムの出現トランザクションIDリスト（posting list）を構築し、
k>=2ではposting listの交差で対象トランザクションを特定する。

```
前処理: postings[i] = sorted list of txn indices where i in d_n
k>=2:   txn_ids(P) = postings[i1] ∩ postings[i2] ∩ ...
        -> ソート済みリストのマージ交差: O(Sigma|postings[i]|)
```

| | 現在 | 提案 |
|---|---|---|
| パターンP={i,j}の出現取得 | O(N) | O(\|post_i\| + \|post_j\|) |
| p_item=0.10の場合 | N | ~0.2N |

### アイデア2: 適応的サポート評価（接頭辞和 vs ストライド）

**問題**: 現在のストライドは各評価位置でO(log |L|)の二分探索を行う。

**提案**: データ密度に応じて接頭辞和スキャンとストライド+二分探索を切り替える。

#### 接頭辞和スキャン

```
occ[t] = L内で時刻tに出現する回数
ps[t]  = cumsum(occ)
count(l, l+W) = ps[l+W] - ps[l-1]  -> O(1)
全lを走査: O(T)
```

#### 計算量比較（1空間開始点あたり）

| | ストライド+二分探索 | 接頭辞和スキャン |
|---|---|---|
| 構築 | - | O(\|L\| + T) |
| 1回のサポート評価 | O(log \|L\|) | O(1) |
| 合計 | O(S * log \|L\|) | O(T) |

S = ストライドのステップ数

- 密データ (S ~ T): ストライド = O(T log |L|) vs 接頭辞和 = O(T) -> 接頭辞和が log|L| 倍速い
- 疎データ (S << T): ストライド = O(S log |L|) << O(T) -> ストライドが速い

#### 切り替え判定基準

S * log |L| = T を境に切り替え。
事前に |L|/T（時間軸密度）を計算すればO(1)で判定可能。

### アイデア3: 候補制限付き空間配布

**問題**: k>=2で各出現をW_sp個の全空間開始点へ配布するが、区間計算ではC(P)内のみ使う。

**提案**: C(P)をHashSetで保持し、C(P)に含まれない空間開始点をスキップ。
さらにC(P)の時間区間も活用し、候補時間区間外のトランザクションを配布対象から除外。

```
for txn_id in posting_intersection(P):
    t, coords = txns[txn_id]
    if !any_candidate_interval_reachable(t, C(P)): continue
    for s_sp in reachable_spatial_starts(coords) ∩ C(P).keys():
        L_P[s_sp].push(t)
```

### アイデア4: ビットセットアイテム判定

**問題**: `tx.items.contains(&item)` が線形探索 O(|d_n|)。

**提案**: トランザクションのアイテム集合をu64ビットマスクに変換。AND 1命令で判定 O(1)。

### アイデア5: rayon並列化

k=1の各アイテム処理、k>=2の各候補処理は独立 -> par_iter で並列化。

---

## k>=2での接頭辞和の制約

接頭辞和は合成できない:

```
I_{i,j}[cell] != min(I_i[cell], I_j[cell])
```

同一セルにiのみ/jのみのトランザクションが別々に存在しうるため。
-> k>=2ではアイデア1（転置インデックス）でトランザクションを特定した後に
   I_P格子を構築 -> 接頭辞和 -> O(1)クエリ、という組み合わせが必要。

---

## ワークショップ論文の構成案

**タイトル案**: "Lazy Evaluation Strategies for Multi-Dimensional Apriori-Window"

| Section | 内容 | 対応アイデア |
|---|---|---|
| 1 Introduction | 区間ベースMD-AWのk>=2ボトルネックを指摘 | - |
| 2 Background | arXiv論文を引用、アルゴリズム要約 | - |
| 3.1 Inverted Index | Posting list交差でO(N)->O(Sigma\|post\|) | アイデア1 |
| 3.2 Adaptive Support | 接頭辞和 vs ストライドの適応切り替え + 判定基準導出 | アイデア2 |
| 3.3 Candidate-Restricted Distribution | C(P)制限で配布先を削減 | アイデア3 |
| 3.4 Engineering | ビットセット + 並列化 | アイデア4,5 |
| 4 Experiments | 各最適化のアブレーション + 総合speedup | 全て |
| 5 Conclusion | - | - |

実験: Chicago Crime / NYPD 等の実データで各最適化ON/OFFのアブレーション。
既存コードに use_t_stride, use_apriori_prune 等のフラグがあるので同様の設計で制御可能。

---

## 関連する実装ファイル

| ファイル | 関連箇所 |
|---|---|
| `apriori_window_md/src/md_apriori.rs` | `build_spatial_t_events_for_pattern_nd` (ボトルネック1,2), `find_dense_itemsets_nd` (メインループ) |
| `apriori_window_1d/src/interval.rs` | `compute_dense_intervals_multiset` (ストライド+二分探索), `compute_dense_intervals_with_candidates_multiset` |
| `apriori_window_1d/src/util.rs` | `lower_bound`, `upper_bound` (二分探索) |

---

## 次のアクション

1. DSAA 2026 投稿を完了する（5/1）
2. DSAA通知後にarXiv投稿準備（タイトル・アブスト微修正）
3. アイデア1（転置インデックス）を実装し、speedup を計測
4. アイデア2（接頭辞和 vs ストライド適応選択）を実装し、crossover 実験
5. アイデア3（候補制限付き空間配布）を実装
6. アブレーション実験で各最適化の寄与を分離
7. CIKMワークショップ論文を執筆（9月中旬目標）
