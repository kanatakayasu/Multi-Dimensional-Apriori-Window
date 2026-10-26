# DSAA2026 発表骨子

**タイトル**: Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions
**発表時間**: 15〜17分（目安 24枚）
**想定聴衆**: データマイニング研究者（Apriori は既知、時空間データは多様な背景）

---

## スライド一覧と詳細骨子

---

### [S01] タイトルスライド（30秒）

**Key Message (EN)**:
> "We present a method that answers both *what* is densely co-occurring and *where and when* — exactly, over any number of dimensions."

**内容**: 論文タイトル・著者・所属・DSAA 2026

---

### [S02] 動機（1.5分）

**見出し**: Motivation — The "What, When, Where, Action" Question

**Key Message (EN)**:
> "Analysts need to know *what* is co-occurring and *where & when* — simultaneously. Neither answer alone is actionable."

**スライド本文**

| Domain | **What** | **When** | **Where** | **Action** |
|---|---|---|---|---|
| Retail | Beer + Chips | Year-end (wk 46–52) | Urban stores 0–9 | Stock up; run coupon |
| Crime | Assault + Battery | Summer weekend nights | South/West Side | Deploy patrol |
| Earthquake | Shallow M>3 + aftershocks | Days after major event | Pacific NW fault zone | Issue warning; inspect bridges |

**使う図**: fig1_motivating

---

### [S03] 既存手法では答えられない（2分）

**見出し**: Existing Methods Cannot Answer Both Questions

**Key Message (EN)**:
> "Pattern mining cannot output regions. Region detection cannot enumerate itemsets. Structural incompatibility."

**スライド本文**

| カテゴリ | 代表手法 | P を出せるか | R(P) を出せるか |
|---|---|---|---|
| 頻出パターンマイニング | Apriori, FP-Growth | ✓ | ✗（グローバルのみ） |
| 局所密集区間 | Apriori-Window | ✓ | 1D のみ |
| 密部分テンソル | M-Zoom | △（偽陽性あり） | 直積ブロックのみ |
| 空間統計 | LISA, Getis-Ord G* | ✗ | 空間軸のみ |
| 時空間クラスタリング | ST-DBSCAN | ✗ | 任意形状（窓定義と不整合） |

---

### [S04] 本研究の貢献（45秒）

**見出し**: This Paper — Multi-Dimensional Apriori-Window

**Key Message (EN)**:
> "Three techniques → exactly enumerate all (P, R(P)) pairs over any d-dimensional grid."

**スライド本文**

3つの技法:
1. 固定空間開始点ごとの **1次元多重集合還元**
2. **(k−1)-部分集合 interval map 交差**による Apriori 枝刈り
3. **重複考慮 t 軸ストライド**

---

### [S05] 多次元トランザクションデータとは？（1分）

**見出し**: What Is Multi-Dimensional Transaction Data?

**Key Message (EN)**:
> "A transaction = coordinate vector + itemset. Extend from 1D time to d-dim by adding spatial axes. One discretization step — all machinery applies."

**スライド本文**（左右2分割）

**【左】1次元トランザクションデータ**

```
時間軸
─────────────────────────────▶ t
 t=1      t=3    t=5    t=7
{A,B}    {A,C}  {A,B,C} {B}

トランザクション = (時刻 t, アイテムセット)
窓 = [l, l+W]
```

**【右】2次元トランザクションデータ（時間 × 空間）**

```
space
bin
 2 │ {A,B}   ·    {A}
 1 │  {B}  {A,B,C} {B}
   └──────────────────▶ time bin
     wk1   wk2   wk3

トランザクション = (time_bin, space_bin, アイテムセット)
窓 = [s₀,s₀+W₀] × [s₁,s₁+W₁]
```

**メッセージ**:
- 1次元: 時間軸のみ
- d次元: **空間座標軸を追加**するだけ
- 連続値座標 → **等幅ビン離散化**（唯一の前処理）

**発表者メモ**: 「後の定義スライド（S06）や 1D 背景（S09）の前提として、データのイメージを共有する。グリッド図で直感的に伝える」

---

### [S06] 頻出パターンと密集パターンの違い（1分）

**見出し**: From Frequent Pattern to Dense Pattern

**Key Message (EN)**:
> "Frequent pattern = global count ≥ θ, no time info. Dense pattern = window count ≥ θ somewhere — gives both *what* and *when/where*."

**スライド本文**

| | 頻出パターン（Frequent） | 密集パターン（Dense） |
|---|---|---|
| サポート定義 | sup(P) = 全期間の出現数 | sup(P, l, W) = 窓 [l, l+W] 内の出現数 |
| 密集条件 | sup(P) ≥ θ（全体） | ∃l : sup(P, l, W) ≥ θ（局所） |
| 出力 | パターン P のみ | **(P, R_θ(P))** — パターン＋密集領域 |
| 時間情報 | なし | **いつ密集するか** を特定 |
| 空間情報 | なし | **どこで密集するか** を特定 |

**密集パターン**: R_θ(P) ≠ ∅ となる P

**密集領域**: R_θ(P) = {(s_sp, [a_j, b_j+W₀])} — 全空間開始点にわたる密集区間の集合

**発表者メモ**: 「頻出パターンは『何が多い』しか答えない。密集パターンは『何が・いつ・どこで』を同時に答える。これが本研究の出発点」

---

### [S07] Apriori 特性：反単調性（パターンレベル）（1分）

**見出し**: The Apriori Property — Anti-Monotonicity Enables Pruning

**Key Message (EN)**:
> "If a pattern is dense, all its subsets are dense. If any subset is not dense, the pattern cannot be dense — prune without evaluation."

**スライド本文**

**反単調性**:
> P が密集 ⟹ P のすべての部分集合 Q も密集

**対偶（枝刈りの根拠）**:
> ある部分集合 Q ⊂ P が非密集 ⟹ P は非密集 → **評価なしにスキップ**

```
アイテムセット格子

         {A,B,C}   ← {B,C} が非密集なら評価不要
        /   |   \
     {A,B}{A,C}{B,C}✗
      /    |    \
    {A}   {B}   {C}
```

**発表者メモ**: 「古典的 Apriori の性質。違いは窓内サポートに基づく点。S08（領域版）と S15（技法2）への橋渡し」

---

### [S08] ★ Apriori 特性：密集領域への拡張（領域レベル）（1分）

**見出し**: Apriori Property on Dense Regions — Only Evaluate Inside the Intersection

**Key Message (EN)**:
> "The dense region of P is *contained within* the intersection of its subsets' dense regions — only evaluate inside that intersection. Empty intersection → skip entirely."

**スライド本文**

補題1 を領域に適用すると:
> R_θ(P)[s_sp] ⊆ ∩_{Q ⊂ P} R_θ(Q)[s_sp]

**具体例**（s_sp 固定、時間軸）:

```
R_θ({A}) :  ████░░░░░████░░░░░
            [10  30]  [50  70]

R_θ({B}) :  ░████░░░░░░████░░░
            [15    40]  [60  80]

∩（候補）:  ░████░░░░░░████░░░
            [15 30]   [60 70]

R_θ({A,B}): 必ず [15,30] ∪ [60,70] の内側に収まる
```

**2つの帰結**:
1. {A,B} の L 構築・評価を **候補区間内だけ** に限定 → 計算量削減
2. 積集合 = ∅ → **{A,B} は密集しえない → 多重集合構築なしでスキップ**

**→ これが技法2（S15）の「候補 interval map 交差」として実装される**

**発表者メモ**
- 「S07 は『評価するかどうか』を決める。S08 は『どこで評価するか』を決める」
- S15（技法2）の布石として強調する

---

### [S09] 1次元 Apriori-Window の復習（1.5分）

**見出し**: Background — 1D Apriori-Window [Takahashi et al.]

**Key Message (EN)**:
> "1D Apriori-Window: count in a sliding window → collect dense start positions → output dense intervals. Time axis only."

**スライド本文**

- **区間サポート**: `sup(P, l, W) = |{t ∈ occ(P) : l ≤ t ≤ l+W}|`
- **密集開始点集合**: `T_θ(P) = {l : sup(P, l, W) ≥ θ}`
- **密集区間**: 最大連続成分 [a, b] → [a, b+W]

**例**: occ={1,2,3,5,7,8}, W=3, θ=2 → T_θ={0,1} → 密集区間 **[0, 4]**

**限界**: 1次元（時間軸）のみ

**発表者メモ**: 「S06 の定義を1次元で具体化。1D の2技法（S10・S11）を次ページで説明する」

---

### [S10] 1D 技法①：t 軸ストライド（1分）

**見出し**: 1D Technique 1 — t-Axis Stride (Gap-Jump)

**Key Message (EN)**:
> "Skip non-dense gaps by jumping l to the next useful position — avoids scanning every window."

**スライド本文**

**問題**: l を1ずつ増やすと O(T) 回の窓チェックが必要

**ストライドの考え方**: 非密集ならジャンプ、密集なら次へ

**例**: occ(AB) = {1, 2, 8}, W=3, θ=2

```
l=1  [1,4]  → {1,2}   → count=2 ✓ dense  → 出力、l+1 へ
l=2  [2,5]  → {2}     → count=1 ✗        → ジャンプ: l ← 8-3 = 5
l=5  [5,8]  → {8}     → count=1 ✗        → 終了

T_θ = {1}  →  密集区間 [1, 4]
```

| | チェック回数 |
|---|---|
| ストライドなし | l=1,2,3,4,5,6,7,8 → **8回** |
| ストライドあり | l=1,2,5 → **3回** |

**ポイント**: `l ← max(l+1, L[next] − W)` で次の出現が窓に入る最小の l へ飛ぶ

**発表者メモ**: 「この "ギャップジャンプ" が技法3（S16）で重複ありに拡張される」

---

### [S11] 1D 技法②：Apriori パターン枝刈り（1分）

**見出し**: 1D Apriori — (k-1)-Subset Check

**Key Message (EN)**:
> "Level-wise: only generate k-itemset candidates from dense (k-1)-itemsets. Non-dense subset → skip the superset."

**スライド本文**

**アイテム**: {A, B, C}、例として {C} が非密集とする

```
k=1  {A}✓  {B}✓  {C}✗
           ↓
k=2  候補: {A,B} のみ
     {A,C}・{B,C} は {C}✗ なので生成せずスキップ
           ↓
k=3  {A,B,C} は {A,C} が存在しないのでスキップ
```

**効果**: アイテム数 |I| が増えると候補数は指数的に増えるが、
Apriori 枝刈りにより実際に評価する集合数を大幅に削減

**発表者メモ**: 「S07 の抽象的な性質をここで 1D 具体例として確認。技法2（S15）では領域レベルにも拡張する」

---

### [S12] 多次元トランザクションデータ（形式定義）（1分）

**見出し**: Multi-Dimensional Transaction Data — From 1D to d-Dimensions

**Key Message (EN)**:
> "A d-dim transaction carries a coordinate vector + itemset. Discretize continuous coordinates into bins — that is the only pre-processing step."

**スライド本文**

| | 1次元 | d次元（本研究） |
|---|---|---|
| トランザクション | (t, items) | (b = (time, space₁,…,spaceₐ₋₁), items) |
| 窓 | [l, l+W] | [s₀,s₀+W₀] × [s₁,s₁+W₁] × … |
| 密集領域 | 時間区間 | (空間開始点, 時間区間) の集合 |

**具体例**（d=3: 時間×緯度ビン×経度ビン）:

```
(week=46, lat_bin=3, lon_bin=7) → {Beer, Chips}
(week=47, lat_bin=3, lon_bin=7) → {Beer, Chips}
  ↑ 前処理：連続座標を等幅ビンに離散化するだけ
```

**次元の例**: 地理（緯度・経度）/ カテゴリ（区・店舗ID）/ 物理（深さ d=4）

---

### [S13] 問題定義：d次元への拡張（1.5分）

**見出し**: Problem Definition — d-Dimensional Dense Region

**Key Message (EN)**:
> "Extend to d-dim hyperrectangle. Anti-monotonicity carries over."

**スライド本文**

- **d次元サポート**: 時間窓 × 空間窓 内の出現数
- **密集領域**: R_θ(P) = {(s_sp, [a_j, b_j+W₀])}

**解きたい問題**: D, W, θ → 全 P の R_θ(P) を完全列挙

**Apriori 単調性** (補題1): Q ⊂ P ⟹ T_θ(P, s_sp) ⊆ T_θ(Q, s_sp)

**使う図**: fig2_1d_reduction（左半分）

---

### [S14] 技法1：固定空間開始点ごとの1D還元（1.5分）

**見出し**: Technique 1 — 1D Reduction per Fixed Spatial Start Point

**Key Message (EN)**:
> "Slice the d-dim data per spatial start point → each slice becomes a 1D multiset → solve with 1D Apriori-Window."

**スライド本文**

- 空間開始点 s_sp を固定 → 多重集合 **L_P(s_sp)** を構築
- d次元問題 = 複数の「重複タイムスタンプを許す 1D 問題」

**コスト**: 1出現 → 最大 W_sp = ∏(W_k+1) 個の空間開始点 → **O(N_P · W_sp)** に増大

**使う図**: fig2_1d_reduction（全体）

---

### [S15] 技法2：Apriori 枝刈り（候補 interval map 交差）（1.5分）

**見出し**: Technique 2 — Apriori Pruning via Interval Map Intersection

**Key Message (EN)**:
> "Candidate interval map = intersection of (k-1)-subset dense regions. Empty → skip. Non-empty → evaluate only inside."

**スライド本文**

**候補 interval map**（S08 の形式化）:
```
C(P, s_sp) = ∩ { R_θ(Q)[s_sp] : Q ∈ (k-1)-subsets of P }
```

**2段階の枝刈り**（S07 + S08 の統合）:
- 全 s_sp で C = ∅ → **パターンレベルでスキップ**（多重集合構築なし）
- C ≠ ∅ → **候補区間内だけ精密評価**（領域レベルで絞る）

**発表者メモ**: 「S07 は評価するかどうか。S08 はどこで評価するか。本スライドが両方を実装」

---

### [S16] 技法3：重複考慮 t 軸ストライド（2分）

**見出し**: Technique 3 — Duplicate-Aware t-Stride

**Key Message (EN)**:
> "Two-branch stride: bulk-output a guaranteed dense block, or gap-jump."

**スライド本文**

**問題**: 技法1の射影により同一 t が複数回入る → S10 のストライドがそのまま使えない

**2分岐ストライド** (L={{1,2,2,3,3,8}}, W₀=3, θ=4):

| 状態 | c | 処理 |
|---|---|---|
| **密集** | c ≥ θ | 余剰 (c−θ) でブロック右端を算出 → 一括出力 |
| **非密集** | c < θ | l ← max(l+1, L[next]−W₀) |

**使う図**: fig3_t_stride

---

### [S17] アルゴリズム全体（1分）

**見出し**: Full Algorithm — Multi-Dimensional Apriori-Window

**Key Message (EN)**:
> "Wrap the 1D solver over spatial start points; apply Apriori pruning at each level."

**スライド本文**

```
for i in I:               # k=1
    build L_i(s_sp); run t-stride → R_θ({i})
F_1 = { {i} : R_θ({i}) ≠ ∅ }

k = 2
while F_{k-1} ≠ ∅:
    for P in candidates(F_{k-1}):
        C(P) = ∩ R_θ(Q)[s_sp]    # S15（S08 の実装）
        if C = ∅ for all s_sp: skip  # S07 パターン枝刈り
        build L_P(s_sp)
        run t-stride restricted to C # S08 領域枝刈り
    k++
```

**計算量**: O( Σ_{P∈F} (N_P·W_sp + Ñ_P log Ñ_P + I_P) )

---

### [S18] 実験設計（30秒）

**見出し**: Experiments — Three Evaluations

**Key Message (EN)**:
> "Quality. Scalability. Interpretability."

| | 実験 | 目的 |
|---|---|---|
| EX-1 | 合成データ比較 | 既存手法との質的差異 |
| EX-2 | スケーラビリティ | T / S / d / \|I\| への依存性 |
| EX-3 | 実データ適用 | 解釈可能性（d=3〜4） |

**環境**: Rust release build, Apple M3 (8コア, 24GB RAM)

---

### [S19] EX-1（1）：合成データの設計（1分）

**見出し**: EX-1 — Synthetic Data with Embedded Dense Regions

**Key Message (EN)**:
> "To test exact region recovery, we embed 4-shape GT in synthetic data — proposed outputs the exact solution by definition."

**スライド本文**

**設定**: T=100 × S=100 グリッド、20 GT パターン、W=(20,5)、θ=30

| Shape | 説明 |
|---|---|
| A 矩形 | 固定サイズの直交密集帯 |
| B ドリフト | 時間とともに空間シフト |
| C 断続 | 時間方向に間欠出現 |
| D 拡大 | 時間とともに領域が拡大 |

**比較手法**: EX-1-1（F1）: Colocation, STCP-Miner / EX-1-2（Jaccard）: LISA, MZoom, ST-DBSCAN

---

### [S20] EX-1（2）：結果（2分）

**見出し**: EX-1 — Structural Mismatch, Not a Parameter Issue

**Key Message (EN)**:
> "F1 and Jaccard on synthetic data: proposed 1.00/1.00 vs. baselines ≤0.917/≤0.190 — structural gap, not a tuning issue."

**スライド本文**

**EX-1-1 (F1)**: 提案=1.00、STCP-Miner=0.917、Colocation=0.356

**EX-1-2 (Jaccard)**:

| 手法 | Jaccard | 根本原因 |
|---|---|---|
| **提案** | **1.00** | 定義による厳密解 |
| ST-DBSCAN | ≤0.190 | 非出現セルを系統的に見落とす |
| LISA | ≤0.10 | 全時刻集約 → 時間情報消失 |
| MZoom | 最低 | 直積ブロック制約 → 幅1に収束 |

**使う図**: fig_ex1_heatmap

---

### [S21] EX-2：スケーラビリティ（1.5分）

**見出し**: EX-2 — Linear Scaling up to 10⁸ Transactions

**Key Message (EN)**:
> "To test scalability, we vary N from 10⁴ to 10⁸ — linear scaling, 10⁸ in ~9 min."

**スライド本文**

| 軸 | 範囲 | 結果 |
|---|---|---|
| T | 10²〜10⁵ | N に対してほぼ線形 |
| S | 10〜10⁴ | 同上 |
| d: 2→4 | — | W_sp 25倍、メモリ 1.35倍のみ |
| \|I\|: 20→80 | — | 指数より緩やか（Apriori 枝刈り） |

**ハイライト**: N=10⁸ → **約9分**

**使う図**: fig_ex2_scalability

---

### [S22] EX-3：実データ適用（1.5分）

**見出し**: EX-3 — Real Data: Interpretable Insights across Domains

**Key Message (EN)**:
> "To verify interpretability, we apply to d=3–4 real data — domain-consistent patterns, no labeled GT needed."

**スライド本文**

| データセット | d | 軸（アイテム） | 得られた知見 |
|---|---|---|---|
| Chicago Crime | 3 | 週×緯度ビン×経度ビン（犯罪種別） | ASSAULT+BATTERY が南部・西部に慢性的ホットスポット；3種複合共起 |
| NYPD Crime | 3 | 週×区×警察署管区（犯罪分類） | 重罪+軽犯罪が特定の区×週ウィンドウに集中 |
| NYC 311 | 3 | 週×コミュニティ地区×苦情種別（サービス要求） | 騒音+違法駐車が住宅地区に集中 |
| USGS Earthquake | 4 | 週×緯度ビン×経度ビン×深さビン（マグニチュード階級） | 浅発/中深発地震が深さ軸で分離 |

---

### [S23] 結論（1.5分）

**見出し**: Conclusion

**Key Message (EN)**:
> "Exact. Linear. Interpretable. Two open problems remain."

**スライド本文**

**貢献**: 3技法により全 (P, R(P)) を厳密列挙

| | 実験結果 |
|---|---|
| EX-1 | 提案: F1=1.00, Jaccard=1.00 / 既存: F1≤0.917, Jaccard≤0.190 |
| EX-2 | N=10⁴–10⁸ で線形（10⁸ を約9分） |
| EX-3 | 犯罪・苦情・地震（d=3–4）でドメイン知識と整合 |

**制約**:
- グリッド離散化依存（ビン幅・**W** の選択が結果に影響）
- W_sp・d 増大で O(N·W_sp) コスト増大
- 検出・記述に特化（因果説明は対象外）

**今後の課題**:
1. **適応的パラメータ選択** — 局所統計量から **W**・θ を自動調整
2. **更なる高速化** — O(1) ウィンドウ集約（累積和）＋スライス差分更新

---

### [S24] Q&A

**見出し**: Thank you — Questions?

**Key Message (EN)**:
> "What + When + Where — exactly, efficiently, interpretably."

**内容**: 論文タイトル、GitHub URL、連絡先

---

## タイムライン

| スライド | 内容 | 時間 |
|---|---|---|
| S01 | タイトル | 0:30 |
| S02 | 動機 | 1:30 |
| S03 | 既存手法の限界 | 2:00 |
| S04 | 本研究の貢献 | 0:45 |
| S05 | 多次元トランザクションデータとは？ | 1:00 |
| S06 | 頻出 vs 密集パターン | 1:00 |
| S07 | Apriori 特性（パターンレベル） | 1:00 |
| S08 | Apriori 特性（密集領域への拡張） | 1:00 |
| S09 | 1D 復習 | 1:30 |
| S10 | **★NEW** 1D 技法①: t軸ストライド | 1:00 |
| S11 | **★NEW** 1D 技法②: Apriori パターン枝刈り | 1:00 |
| S12 | 多次元トランザクションデータ（形式定義） | 1:00 |
| S13 | d次元拡張（問題定義） | 1:30 |
| S14 | 技法1（1D還元） | 1:30 |
| S15 | 技法2（枝刈り） | 1:30 |
| S16 | 技法3（t-ストライド） | 2:00 |
| S17 | アルゴリズム全体 | 1:00 |
| S18 | 実験設計 | 0:30 |
| S19 | EX-1 設計 | 1:00 |
| S20 | EX-1 結果 | 2:00 |
| S21 | EX-2 スケーラビリティ | 1:30 |
| S22 | EX-3 実データ | 1:30 |
| S23 | 結論（まとめ＋今後の課題） | 1:30 |
| **合計** | | **~27分** |

> **17〜18分に削る方法**:
> S17 省略（−1分）＋ S19+S20 統合（−1分）＋ S07+S08 を1枚に圧縮（−1分）＋ S10+S11 を1枚に圧縮（−1分）＋ S12+S13 省略（−2.5分）＋ S05 or S12 省略（−1分）

---

## 論理の流れ（1D → d次元）

```
S09  1D Apriori-Window
       ↓
S10  1D 技法①: t軸ストライド（ギャップジャンプ）
S11  1D 技法②: Apriori パターン枝刈り
       ↓ 「d次元に拡張したい」
S14  技法1: d次元 → 1D 還元（計算量 W_sp 倍に増大）
       ↓ 「計算爆増を抑えたい」
S15  技法2: Apriori 領域枝刈り（S07+S08 の実装）→ 大幅削減
       ↓ 「還元で重複タイムスタンプが生じる」
S16  技法3: 重複を許す t軸ストライド（S10 の拡張）
```

---

## S06〜S08 の論理的な流れ

```
S06  頻出 vs 密集パターン
       ↓
S07  Apriori 特性（パターンレベル）
       「P が密集 → 全部分集合も密集」
       ↓ 「これは領域にも成り立つ？」
S08  Apriori 特性（領域レベル）
       「R_θ(P) ⊆ ∩ R_θ(部分集合)」
       ↓ 「どう実装する？」
S15  技法2: 候補 interval map 交差
```

---

## 使う図の対応表

| スライド | 図ファイル | 用途 |
|---|---|---|
| S02 | `fig/fig1_motivating.tex` | 動機付けの例 |
| S13〜14 | `fig/fig2_1d_reduction.tex` | d次元 → 1D還元 |
| S16 | `fig/fig3_t_stride.tex` | 重複考慮ストライドの2分岐 |
| S20 | `fig/fig_ex1_heatmap.pdf` | EX-1 F1/Jaccard ヒートマップ |
| S21 | `fig/fig_ex2_scalability.pdf` | EX-2 スケーラビリティ棒グラフ |
| S08 | （新規作成） | 時間軸で R(A)∩R(B) の候補区間を示す図 |
| S05 | （新規作成） | 1D TD vs 2D TD の左右比較図 |

---

## Key Messages 一覧（発表練習用）

| スライド | Key Message (EN) |
|---|---|
| S01 | Answer both *what* and *where & when* — exactly. |
| S02 | Analysts need all four: What, When, Where, Action. |
| S03 | Pattern mining lacks regions. Region detection lacks itemsets. |
| S04 | Three techniques → exact enumeration of (P, R(P)). |
| S05 | Transaction = coordinate vector + itemset. Add spatial axes → d-dim. |
| S06 | Frequent = global count. Dense = window count somewhere → (P, R(P)). |
| S07 | If any subset is not dense → prune without evaluation. |
| S08 | R_θ(P) ⊆ ∩ R_θ(subsets). Only evaluate inside intersection. |
| S09 | 1D: count → dense intervals. Time axis only. |
| S10 | Skip non-dense gaps: jump l to next useful position. |
| S11 | Level-wise: only generate candidates from dense subsets. |
| S12 | d-dim transaction = coordinate vector + itemset. Discretize → ready. |
| S13 | Extend to d-dim hyperrectangle. Anti-monotonicity carries over. |
| S14 | Slice d-dim data per spatial start point → 1D multiset → solve with 1D Apriori-Window. |
| S15 | C(P) = ∩ R(subsets). Empty → skip. Non-empty → restrict. |
| S16 | Two-branch stride: dense block or gap-jump. Handles duplicates. |
| S17 | Wrap 1D solver + Apriori pruning per level. |
| S18 | Quality. Scalability. Interpretability. |
| S19 | To test exact recovery, embed 4-shape GT → exact solution by definition. |
| S20 | F1 & Jaccard: proposed 1.00/1.00 vs. baselines ≤0.917/≤0.190. |
| S21 | To test scalability, vary N 10⁴–10⁸ → linear; 10⁸ in ~9 min. |
| S22 | To verify interpretability, apply to d=3–4 real data → domain-consistent. |
| S23 | Exact. Linear. Interpretable. Two open problems: adaptive params + faster construction. |
| S24 | What + When + Where — exactly, efficiently, interpretably. |
