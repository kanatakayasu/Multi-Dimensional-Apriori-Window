# DSAA2026 発表原稿（12分版）

## 方針

- **Agenda スライド（4枚）はすべてスキップ** → 口頭で "Next, background." 等と言うだけ
- **Apriori Property for Frequent Pattern / Dense Pattern（2枚）はスキップ** → Dense Region の1枚だけ残す
- アニメーションスライドは `[クリック]` と書いた箇所でクリックしながら話す
- 目安時間は速めのペースを想定

---

## Slide 1: Title ⏱ ~20秒

**English:**
Good morning everyone. I'm Kanata Takayasu from Keio University. Today I'll present our work: Multi-Dimensional Apriori-Window — Exact Mining of Dense Itemset Regions over Arbitrary Dimensions.

**日本語訳：**
皆さん、おはようございます。慶應義塾大学の高安奏太です。本日は「多次元 Apriori-Window：任意次元における密集アイテムセット領域の厳密マイニング」をご発表します。

---

## ~~Slide: Agenda~~ → SKIP

---

## Slide 2: Motivation — The "What, When, Where" Question ⏱ ~1分30秒

*（アニメーション3ステップ：What/Where/When → Action → 表。クリックしながら話す）*

**English:**
The core question is: **what** items co-occur, **where**, and **when** — simultaneously.

[クリック] Neither answer alone is actionable. Knowing beer and chips sell together is useful, but knowing it happens specifically in Area A on Friday nights enables a targeted coupon campaign.

[クリック] The same applies to crime analysis — assault and battery in downtown at midnight means deploy patrol — and to epidemiology: fever and cough in District 7 during weeks 12–14 means dispatch a medical team.

We need all three dimensions at once.

**日本語訳：**
核心的な問いは「何が共起しているか、どこで、いつか」をまとめて答えることです。

どちらの答えだけでも行動に繋がりません。ビールとチップスが一緒に売れるという知識は有用ですが、それが「エリアAの金曜夜に」起きているとわかれば、ターゲットを絞ったクーポン施策を打てます。

犯罪分析でも同様です。深夜のダウンタウンで暴行と傷害が多発しているなら巡回を増やし、疫学なら地区7で12〜14週に発熱と咳が集中しているなら医療チームを派遣します。

3つの次元を同時に答える必要があります。

---

## Slide 3: Existing Methods Cannot Answer Both Questions ⏱ ~1分

**English:**
This table summarizes the gap. Existing methods fall into two camps.

Pattern mining methods — Apriori, LPFIM, Apriori-Window — find itemsets, but cannot output dense regions. Region detection methods — SaTScan, FlexScan, ST-DBSCAN — find regions, but cannot enumerate itemsets.

This is a **structural** incompatibility. It cannot be fixed by tuning parameters.

Our method is the first to achieve all three: itemsets, ST dense regions, and arbitrary region shape.

**日本語訳：**
この表がギャップを示しています。既存手法は2つのグループに分かれます。

Apriori、LPFIM、Apriori-Window などのパターンマイニング手法はアイテムセットを発見できますが、密集領域を出力できません。SaTScan、FlexScan、ST-DBSCAN などの領域検出手法は領域を発見できますが、アイテムセットを列挙できません。

これは**構造的**な非互換性であり、パラメータ調整では解決できません。

本手法は、アイテムセット・時空間密集領域・任意形状の3つを同時に達成する初めての手法です。

---

## Slide 4: This Paper — Multi-Dimensional Apriori-Window ⏱ ~40秒

**English:**
We propose three techniques that together exactly enumerate all dense itemsets and their arbitrary-shaped dense regions over any d-dimensional grid.

One: Reduction to 1D per fixed spatial start point.
Two: Apriori pruning via (k-1)-subset interval map intersection.
Three: Duplicate-aware t-axis stride.

**日本語訳：**
私たちは、任意のd次元グリッド上のすべての密集アイテムセットとその任意形状の密集領域を厳密に列挙する3つの技術を提案します。

第一に、固定空間始点ごとの1次元化。
第二に、(k-1)-部分集合区間マップ交差による Apriori 剪定。
第三に、重複を考慮した t 軸ストライド。

---

## Slide 5: Multi-Dimensional Transaction Data ⏱ ~40秒

**English:**
Each transaction is a coordinate vector plus an itemset. In 1D, transactions are ordered along time axis t. In 2D, we add a spatial axis x — and we extend this to arbitrary d dimensions.

**日本語訳：**
各トランザクションは座標ベクトルとアイテムセットの組です。1次元では時刻 t に沿って並びます。2次元では空間軸 x を加えます。これを任意の d 次元に拡張します。

---

## Slide 6: Frequent Pattern & Dense Pattern (table) ⏱ ~30秒

**English:**
Frequent pattern mining counts occurrences globally — it tells us **what** but gives no temporal or spatial information.

Dense pattern mining counts within a sliding window of size W. If any window satisfies the threshold θ, the pattern is dense — and we know exactly **when** and **where**.

**日本語訳：**
頻出パターンマイニングは全体の出現回数をカウントします。**何が**出現するかはわかりますが、時空間情報はありません。

密集パターンマイニングはサイズ W のスライディングウィンドウ内でカウントします。いずれかのウィンドウが閾値 θ を満たせばそのパターンは密集しており、**いつ・どこで**かも正確にわかります。

---

## Slide 7: Frequent Pattern & Dense Pattern (example) ⏱ ~45秒

*（アニメーション4ステップ。クリックしながら話す）*

**English:**
Here's a concrete example with W=4, θ=2.

[クリック] Frequent pattern: AB appears 4 times globally — sup(AB)=4 ≥ θ. AB is frequent.

[クリック] Dense pattern: window [1,4] contains 3 occurrences, [2,5] contains 2. Both meet θ.

[クリック] Window [3,6] contains only 1 — below θ. So the dense region of AB is [1,5], meaning AB is dense during that interval.

**日本語訳：**
W=4、θ=2 の具体例です。

頻出パターン：AB は全体で4回出現します — sup(AB)=4 ≥ θ。AB は頻出です。

密集パターン：ウィンドウ [1,4] に3回、[2,5] に2回出現。どちらも θ を満たします。

ウィンドウ [3,6] は1回のみ — θ 未満。AB の密集領域は [1,5] となり、その区間中に AB が密集していることがわかります。

---

## Slide 8: Apriori Property for Frequent Pattern ⏱ ~30秒

**English:**
Apriori [1] is a seminal work in pattern mining. It introduces the **Apriori property**: if a pattern is frequent, every subset is also frequent. Equivalently — if any subset is *not* frequent, the pattern cannot be frequent. This allows us to prune the search space dramatically.

**日本語訳：**
Apriori [1] はパターンマイニングの代表的な既存研究です。そこで提唱されている **Apriori 特性** とは：あるパターンが頻出であれば、その全部分集合も頻出である、というものです。裏を返せば、ある部分集合が頻出でなければ、そのパターンは頻出になれません。これにより探索空間を大幅に枝刈りできます。

---

## Slide 9: Apriori Property for Dense Pattern ⏱ ~30秒

**English:**
We prove that this property extends to dense patterns. If a pattern is dense, every subset is also dense. And if any subset is *not* dense, the pattern cannot be dense.

This means we can prune candidate itemsets using the same Apriori principle — before evaluating any window.

**日本語訳：**
私たちはこの特性が密集パターンにも適用可能であることを証明しました。あるパターンが密集であれば、その全部分集合も密集です。ある部分集合が密集でなければ、そのパターンは密集になれません。

これにより、ウィンドウを評価する前に、同じ Apriori 原理でアイテムセット候補を枝刈りできます。

---

## Slide 10: Apriori Property for Dense Region ⏱ ~40秒

**English:**
We further prove a stronger result: the **dense region** of a pattern is contained within the intersection of its subsets' dense regions.

So for AB, we only search within the overlap of A's and B's dense regions. If this intersection is empty, we skip AB entirely — no scanning needed.

**日本語訳：**
さらに強い結果も証明しました：パターンの**密集領域**は、その部分集合の密集領域の交差に必ず含まれます。

つまり AB については、A の密集領域と B の密集領域の重なりの中だけを探索すればよいのです。交差が空ならば、AB を完全にスキップできます。

---

## Slide 11: Multi-Dimensional Apriori-Window Overview ⏱ ~30秒

**English:**
Here's how the three techniques connect. Reducing d-dim to 1D introduces two problems: increased computational cost, and broken t-axis stride. We address each with interval map intersection and duplicate-aware stride respectively.

**日本語訳：**
3つの技術の関係を示します。d次元を1次元に削減すると2つの問題が生じます：計算コストの増大と、t 軸ストライドの不整合。これをそれぞれ区間マップ交差と重複対応ストライドで解決します。

---

## Slide 12: Reduction to 1D ⏱ ~1分30秒

*（アニメーション多数。クリックしながら手短に説明）*

**English:**
We fix each spatial start point and collect all transactions within the spatial window — creating a 1D multiset.

[クリック×複数] For each start point, we slide the spatial window across x and collect the corresponding column. Each column becomes an independent 1D sequence.

[クリック] Then we slide the t-axis window over each 1D sequence to find dense time intervals. This decomposes the d-dimensional problem into many independent 1D problems.

**日本語訳：**
各空間始点を固定し、空間ウィンドウ内のすべてのトランザクションを収集して1次元多重集合を作ります。

各始点に対して空間ウィンドウを x 方向にスライドし、対応する列を収集します。各列が独立した1次元系列になります。

次に t 軸ウィンドウを各1次元系列でスライドして密集時間区間を探します。d次元の問題が多数の独立した1次元問題に分解されます。

---

## Slide 13: Determine Density Using Sliding Window ⏱ ~45秒

*（アニメーション4ステップ。クリックしながら）*

**English:**
The sliding window scans along t. For each position l, we count pattern occurrences in [l, l+W].

[クリック] [1,4]: 4 occurrences — dense.
[クリック] [2,5]: 3 — dense.
[クリック] [3,6]: 2 — dense.
[クリック] [4,7]: 1 — not dense.

The dense region is [1,6].

**日本語訳：**
スライディングウィンドウが t 軸を走査します。各位置 l で [l, l+W] 内のパターン出現回数をカウントします。

[1,4]: 4回 — 密集。[2,5]: 3回 — 密集。[3,6]: 2回 — 密集。[4,7]: 1回 — 非密集。

密集領域は [1,6] です。

---

## Slide 14: Duplicate-Aware t-Axis Stride ⏱ ~1分

*（アニメーション多数。2つの例を示す）*

**English:**
Scanning every window is expensive. We exploit structure to skip positions.

[クリック] When the window count is well above θ, shifting l by one only removes one occurrence from the left — the window stays dense. We can jump ahead to skip these guaranteed-dense positions.

[クリック] Conversely, when count is well below θ, we can jump l forward past the guaranteed non-dense positions.

[クリック] When the count is borderline — could go either way — we must scan normally.

This stride mechanism substantially reduces the number of windows evaluated.

**日本語訳：**
すべてのウィンドウをスキャンするのは非効率です。構造を利用して位置をスキップします。

ウィンドウのカウントが θ を十分上回っている場合、l を1つずらしても左端の出現が1つ抜けるだけなのでウィンドウは密集のまま。確実に密集している位置をジャンプできます。

逆にカウントが θ を十分下回っている場合、確実に非密集な位置を飛ばして l を前進させられます。

カウントが境界値の場合は、通常通りスキャンします。

このストライド機構により、評価するウィンドウ数を大幅に削減します。

---

## Slide 15: Duplicate-Aware Stride Formula ⏱ ~30秒

**English:**
Formally: when count ≥ θ, we jump l to occ(Pattern, id_left + surplus) + 1. When count < θ, we jump to max(l+1, occ(Pattern, id_right+1) − W). These jumps are proven to miss no dense region.

**日本語訳：**
形式的には：カウント ≥ θ のとき、l を occ(Pattern, id_left + surplus) + 1 へジャンプ。カウント < θ のとき、max(l+1, occ(Pattern, id_right+1) − W) へジャンプ。このジャンプで密集領域を見落とさないことが証明されています。

---

## Slide 16: Apriori Pruning via (k-1)-Subset Interval Map Intersection ⏱ ~40秒

**English:**
For k-itemsets, we intersect the dense regions of all (k-1)-subsets. The candidate region for AB is bounded by the intersection of A's and B's interval maps. Empty intersection means we skip the candidate entirely.

This dramatically reduces the number of (start point, window) pairs to evaluate.

**日本語訳：**
k-アイテムセットに対して、すべての (k-1)-部分集合の密集領域を交差させます。AB の候補領域は A と B の区間マップの交差に絞られます。交差が空なら候補を完全に枝刈りします。

これにより評価すべき（空間始点、ウィンドウ）ペアの数を劇的に削減します。

---

## Slide 17: EX-1 — Exactness Verification ⏱ ~1分

*（セットアップスライド：口頭で軽く触れてから結果スライドへ）*

**English:**
We verify correctness on synthetic data with four ground-truth region shapes — rectangle, drift, intermittent, and expanding — embedded in a 100×100 grid with 20 GT patterns.

Results: our method achieves **F1 = 1.000** for all shapes — perfect detection. Baselines Colocation and STCP-Miner degrade significantly on complex shapes; Expanding drops to F1 = 0.356 and 0.601.

For region recovery, our Jaccard index is **1.000**. All baselines fall below 0.20 — confirming the structural incompatibility we identified earlier.

**日本語訳：**
4種類の真値領域形状（矩形・ドリフト・断続・拡大）を100×100グリッドに埋め込んだ合成データで正確性を検証します（GT パターン20個）。

結果：本手法はすべての形状で **F1 = 1.000** を達成 — 完全検出。ベースラインの Colocation と STCP-Miner は複雑な形状で大きく劣り、Expanding では F1 = 0.356 と 0.601 まで低下します。

領域復元においても Jaccard 指数は **1.000**。すべてのベースラインは 0.20 未満 — 先ほど指摘した構造的非互換性を裏付けています。

---

## Slide 18: EX-2 — Scalability ⏱ ~40秒

**English:**
We scale N from 10^4 to 10^8. Runtime grows linearly. At 10^8 transactions, runtime is approximately 9 minutes with modest memory.

Across all axes — T, S, d, and itemset size — scaling remains practical.

**日本語訳：**
N を 10^4 から 10^8 まで変化させます。実行時間は線形に増加します。10^8 トランザクションで約9分、メモリも現実的な範囲です。

T、S、d、アイテムセットサイズのすべての軸でスケーリングは実用的な水準です。

---

## Slide 19: EX-3 — Application to Real-World Data ⏱ ~45秒

*（セットアップスライドは口頭で触れるだけ、結果スライドを中心に話す）*

**English:**
We apply our method to four real-world datasets with d = 3 to 4.

Chicago Crime: ASSAULT and BATTERY form a chronic hotspot in the South/West Side. NYPD Crime: felony and misdemeanor co-occur in specific borough × week windows. NYC 311: noise and illegal parking cluster in residential districts. USGS Earthquake: shallow and mid-depth quakes separate cleanly along the depth axis.

All findings are domain-consistent — with no labeled ground truth required.

**日本語訳：**
d = 3〜4の実世界データセット4つに適用します。

Chicago Crime：暴行と傷害がサウス・ウェストサイドで慢性的なホットスポットを形成。NYPD Crime：重罪と軽犯罪が特定の地区×週ウィンドウで共起。NYC 311：騒音と不法駐車が住宅地区でクラスター化。USGS Earthquake：浅発地震と中深発地震が深度軸で明確に分離。

すべての発見が、ラベル付き真値なしでドメイン整合的です。

---

## Slide 20: Conclusion ⏱ ~40秒

**English:**
To summarize: we proposed Multi-Dimensional Apriori-Window — the first method to exactly enumerate dense itemsets and their arbitrary-shaped dense regions over d-dimensional grids.

Three core techniques: 1D reduction, interval map intersection, and duplicate-aware stride. Together they achieve exact results with linear scalability up to 10^8 transactions.

Limitations: grid discretization and increasing cost in high dimensions. Future work: adaptive parameter selection and further acceleration through incremental updates.

Thank you.

**日本語訳：**
まとめると：d次元グリッド上で密集アイテムセットと任意形状の密集領域を厳密に列挙する初の手法、多次元 Apriori-Window を提案しました。

3つの中核技術 — 1次元化、区間マップ交差、重複対応ストライド — を組み合わせ、10^8 トランザクションまで線形スケールで厳密な結果を達成します。

制限としてはグリッド離散化と高次元での計算コスト増大があります。将来課題は適応的パラメータ選択と増分更新による高速化です。

ありがとうございました。

---

## タイムライン概算

| スライド | 目安時間 |
|---------|---------|
| Title | 20秒 |
| Motivation | 1分30秒 |
| Existing Methods | 1分 |
| This Paper | 40秒 |
| Transaction Data | 40秒 |
| FP & Dense Pattern (table) | 30秒 |
| FP & Dense Pattern (example) | 45秒 |
| Apriori Property (Frequent Pattern) | 30秒 |
| Apriori Property (Dense Pattern) | 30秒 |
| Apriori Property (Dense Region) | 40秒 |
| Method Overview | 30秒 |
| Reduction to 1D | 1分30秒 |
| Sliding Window | 45秒 |
| Duplicate-aware Stride | 1分 |
| Stride Formula | 30秒 |
| Apriori Pruning | 40秒 |
| EX-1 | 1分 |
| EX-2 | 40秒 |
| EX-3 | 45秒 |
| Conclusion | 40秒 |
| **合計** | **~14分30秒** |

> **注:** Apriori Property 3枚を追加したため、合計は約14分30秒になります。12分に収めるには、Reduction to 1D のアニメーションを最終状態だけに短縮（-30秒）、Stride Formula を口頭のみ（-30秒）、EX-3 を1文に圧縮（-30秒）などで調整してください。
