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
  5. (k-1)-subset interval map を交差 -> C(P)             O(I_P)  [DSAA2026で改善済み]
  6. 全N件を再スキャン -> P を含むトランザクション抽出     <-- ボトルネック1
  7. C(P) に含まれる空間開始点のみへ配布                   [DSAA2026で改善済み]
  8. C(P) に含まれる空間開始点のみで区間計算               O(候補区間内のみ)
```

### DSAA2026 で解消済みのボトルネック

以下の2点はDSAA2026投稿版で実装・論文に反映済み：

1. **(k-1)-subset interval map 交差**（旧: singleton交差）:
   k=3のパターン{A,B,C}の候補区間を求める際、旧版はA,B,Cのsingleton interval mapを交差していた。
   改善版では{A,B}, {A,C}, {B,C}の(k-1)-subset interval mapを交差する。
   R({A,B}) ⊆ R({A}) ∩ R({B}) なので、常により狭い（または等しい）候補区間が得られる。

2. **候補制限付き空間配布**:
   旧版はパターンPの出現トランザクションを全W_sp個の空間開始点に配布していた。
   改善版ではC(P)のキー（空間開始点）をHashSetで保持し、C(P)に含まれる空間開始点のみに配布する。

### 残存ボトルネック

核心的な無駄: ステップ6で依然として全N件をスキャンしている。

---

## スピードアップアイデア

### アイデア1: 転置インデックス（HashMap）によるk>=2フルスキャン排除

**問題**: `build_spatial_t_events_for_pattern_nd` が候補パターンごとに全N件をスキャンする。

**提案**: k=1で各アイテムの出現トランザクションIDリスト（posting list）を
HashMap<アイテム, Vec<トランザクションID>> として構築し、
k>=2ではposting listの交差で対象トランザクションを特定する。

```
前処理: postings: HashMap<i64, Vec<usize>>
        postings[i] = sorted list of txn indices where i in d_n
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

### アイデア3: 候補制限付き空間配布 → DSAA2026で実装済み

**状態**: DSAA2026投稿版に含めた。C(P)のキーをHashSetで保持し、
C(P)に含まれる空間開始点のみに配布する。

**ワークショップでの発展**: 時間区間による追加フィルタリング。
C(P)の時間区間も活用し、候補時間区間外のトランザクションを配布対象から除外。

```
for txn_id in posting_intersection(P):
    t, coords = txns[txn_id]
    if !any_candidate_interval_reachable(t, C(P)): continue
    for s_sp in reachable_spatial_starts(coords) ∩ C(P).keys():
        L_P[s_sp].push(t)
```

### アイデア4: ハッシュ木による全候補一括処理

**問題**: k>=2のメインループで候補パターンを1つずつ逐次処理し、
各候補ごとに全トランザクション（またはposting list交差結果）をスキャンする。
候補C個 × トランザクションスキャン = C回の独立ループ。

```
現在 (md_apriori.rs:514-545):
for pattern in candidates:       // C個の候補を逐次処理
    for tx in txns:              // 毎回N件（またはposting交差分）スキャン
        if pattern ⊆ tx.items:
            distribute(tx, pattern)
合計: C * N（またはC * |posting交差|）
```

**提案**: 全候補をハッシュ木（Hash Tree）に格納し、
トランザクションを1回スキャンするだけで全候補のマッチングを同時に行う。

```
// 前処理: 全候補をハッシュ木に格納
hash_tree = build_hash_tree(candidates)
//   深さ0: items[0] % bucket_size で分岐
//   深さ1: items[1] % bucket_size で分岐
//   ...
//   葉: 候補パターンのリスト

// トランザクションを1回だけスキャン
for tx in txns:                                    // N回（1回だけ）
    matching = hash_tree.find_subsets(tx.items)     // txに含まれる候補を全検索
    for pattern in matching:
        distribute(tx, pattern, spatial_starts)
```

| | 現在 | ハッシュ木 |
|---|---|---|
| トランザクションスキャン回数 | C * N | N（1回） |
| 候補100個, N=10万 | 1000万回 | 10万回 |

古典的Aprioriで広く使われている手法（Agrawal & Srikant 1994の原論文でも採用）。
MD-AWでは空間配布と組み合わせるため、ハッシュ木のマッチング結果を
そのまま空間開始点への配布に流す設計が必要。

アイデア1（転置インデックス）とは相補的:
- 転置インデックス: 「パターンP → Pを含むトランザクション」を高速に取得
- ハッシュ木: 「トランザクションtx → txに含まれる候補パターン」を高速に取得
データの疎密に応じてどちらが有利かが変わる。

### アイデア5: ビットセットアイテム判定

**問題**: `tx.items.contains(&item)` が線形探索 O(|d_n|)。

**提案**: トランザクションのアイテム集合をu64ビットマスクに変換。AND 1命令で判定 O(1)。
ハッシュ木やposting list交差との組み合わせでも内部判定が高速化される。

### アイデア6: rayon並列化

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

注: アイデア3（候補制限付き空間配布）はDSAA2026で実装済みのため、
ワークショップ論文ではベースラインに含まれる。

| Section | 内容 | 対応アイデア |
|---|---|---|
| 1 Introduction | 区間ベースMD-AWの残存ボトルネック（フルスキャン）を指摘 | - |
| 2 Background | arXiv論文を引用、アルゴリズム要約 | - |
| 3.1 Inverted Index | Posting list交差でO(N)->O(Sigma\|post\|) | アイデア1 |
| 3.2 Adaptive Support | 接頭辞和 vs ストライドの適応切り替え + 判定基準導出 | アイデア2 |
| 3.3 Hash Tree | 全候補一括マッチングでC*N->Nに | アイデア4 |
| 3.4 Temporal Filtering | C(P)の時間区間による配布フィルタ | アイデア3の発展 |
| 3.5 Engineering | ビットセット + 並列化 | アイデア5,6 |
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

1. ~~DSAA 2026 投稿を完了する（5/1）~~ → 進行中（(k-1)-subset交差 + 候補制限付き配布を反映済み）
2. DSAA通知後にarXiv投稿準備（タイトル・アブスト微修正）
3. アイデア1（転置インデックス）を実装し、speedup を計測
4. アイデア2（接頭辞和 vs ストライド適応選択）を実装し、crossover 実験
5. ~~アイデア3（候補制限付き空間配布）を実装~~ → DSAA2026に含めた
6. アイデア4（ハッシュ木）を実装
7. アブレーション実験で各最適化の寄与を分離
8. CIKMワークショップ論文を執筆（9月中旬目標）
