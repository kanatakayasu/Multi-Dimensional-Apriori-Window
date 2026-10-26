# DSAA2026 Presentation Outline (English)

**Title**: Multi-Dimensional Apriori-Window: Exact Mining of Dense Itemset Regions over Arbitrary Dimensions
**Duration**: 15–17 min (23 slides)
**Audience**: Data mining researchers (Apriori assumed known; varied spatio-temporal backgrounds)

---

## Slide-by-Slide Outline

---

### [S01] Title Slide (30 sec)

**Key Message**:
> "We present a method that answers both *what* is densely co-occurring and *where and when* — exactly, over any number of dimensions."

**Content**: Paper title, authors, affiliations, DSAA 2026

---

### [S02] Motivation: The "What, When, Where, Action" Question (1.5 min)

**Heading**: Motivation — From Data to Actionable Insight

**Key Message**:
> "Analysts need to know *what* is co-occurring and *where & when* — simultaneously. Neither answer alone is actionable."

**Slide content**

| Domain | **What** | **When** | **Where** | **Action** |
|---|---|---|---|---|
| Retail | Beer + Chips | Year-end (wk 46–52) | Urban stores 0–9 | Stock up; run coupon |
| Crime | Assault + Battery | Summer weekend nights | South/West Side | Deploy patrol |
| Earthquake | Shallow M>3 + aftershocks | Days after major event | Pacific NW fault zone | Issue warning; inspect bridges |

**Core question**: "Can existing tools answer all four columns at once?"

**Figure**: `fig/fig1_motivating`

---

### [S03] Existing Methods Cannot Answer Both Questions (2 min)

**Heading**: The Structural Gap — Two Lineages, Neither Complete

**Key Message**:
> "Pattern mining cannot output regions. Region detection cannot enumerate itemsets. Structural incompatibility — not fixable by tuning."

**Slide content**

| Category | Method | Outputs P? | Outputs R(P)? | Shape |
|---|---|---|---|---|
| Frequent pattern mining | Apriori, FP-Growth | ✓ | ✗ (global only) | — |
| Local dense interval | Apriori-Window | ✓ | 1D only | interval |
| Dense subtensor | M-Zoom | △ false positives | product block only | rectangle |
| Spatial statistics | LISA, Getis-Ord G* | ✗ | spatial only | arbitrary |
| ST clustering | ST-DBSCAN | ✗ | mismatches window def. | arbitrary |
| **This work** | **MD Apriori-Window** | **✓** | **✓** | **arbitrary** |

---

### [S04] Contributions (45 sec)

**Heading**: This Paper — Multi-Dimensional Apriori-Window

**Key Message**:
> "Three techniques → exactly enumerate all (P, R(P)) pairs over any d-dimensional grid."

**Slide content**

Three techniques:
1. **1D multiset reduction** per fixed spatial start point
2. **Apriori pruning** via (k−1)-subset interval map intersection
3. **Duplicate-aware t-stride**

---

### [S05] What Is Multi-Dimensional Transaction Data? (1 min)

**Heading**: What Is Multi-Dimensional Transaction Data?

**Key Message**:
> "A transaction = coordinate vector + itemset. Extend from 1D time to d-dim by adding spatial axes. One discretization step — all machinery applies."

**Slide content** (two-column visual layout)

**[Left] 1D Transaction Data**

```
Time axis
─────────────────────────────▶ t
 t=1      t=3    t=5    t=7
{A,B}    {A,C}  {A,B,C} {B}

Transaction = (timestamp t, itemset)
Window = [l, l+W]
```

**[Right] 2D Transaction Data (Time × Space)**

```
space
bin
 2 │ {A,B}   ·    {A}
 1 │  {B}  {A,B,C} {B}
   └──────────────────▶ time bin
     wk1   wk2   wk3

Transaction = (time_bin, space_bin, itemset)
Window = [s₀, s₀+W₀] × [s₁, s₁+W₁]
```

**Message**:
- 1D: time axis only
- d-dim: **add spatial coordinate axes**
- Continuous coordinates → **equal-width bin discretization** (only pre-processing step)

**Speaker notes**: "Ground the audience's intuition before the formal definitions in S06. The grid diagram makes the structure immediately clear."

---

### [S06] From Frequent Pattern to Dense Pattern (1 min)

**Heading**: From Frequent Pattern to Dense Pattern

**Key Message**:
> "Frequent pattern = global count ≥ θ, no time info. Dense pattern = window count ≥ θ somewhere — gives both *what* and *when/where*."

**Slide content**

| | Frequent Pattern | Dense Pattern |
|---|---|---|
| Support | sup(P) = total occurrence count | sup(P, l, W) = count within window [l, l+W] |
| Condition | sup(P) ≥ θ (globally) | ∃l : sup(P, l, W) ≥ θ (locally) |
| Output | Pattern P only | **(P, R_θ(P))** — pattern + dense region |
| Temporal info | None | *When* it is dense |
| Spatial info | None | *Where* it is dense |

**Dense pattern**: P such that R_θ(P) ≠ ∅

**Dense region**: R_θ(P) = {(s_sp, [a_j, b_j+W₀])} — dense intervals across all spatial start points

**Speaker notes**: "Frequent pattern answers only *what*. Dense pattern answers *what + when + where* simultaneously. This is the core shift."

---

### [S07] The Apriori Property — Anti-Monotonicity (1 min)

**Heading**: The Apriori Property — Anti-Monotonicity Enables Pruning

**Key Message**:
> "If a pattern is dense, all its subsets are dense. Equivalently: if any subset is not dense, the pattern cannot be dense — prune it without evaluation."

**Slide content**

**Anti-Monotonicity**:
> P is dense ⟹ every subset Q ⊂ P is also dense

**Contrapositive (pruning rule)**:
> Some subset Q ⊂ P is *not* dense ⟹ P cannot be dense → **skip without evaluation**

```
Itemset lattice ({A,B,C})

         {A,B,C}   ← if {B,C} is not dense → skip
        /   |   \
     {A,B}{A,C}{B,C}✗
      /    |    \
    {A}   {B}   {C}
```

**Level-wise**: k=1 → evaluate all; k=2 → generate from F₁; k=3+ → repeat

**Speaker notes**: "Classical Apriori — window support instead of global support. Bridge to S08 (region version) and S13 (Technique 2)."

---

### [S08] Apriori Property on Dense Regions — Region Intersection (1 min)

**Heading**: Apriori Property on Dense Regions — Only Evaluate Inside the Intersection

**Key Message**:
> "The dense region of P is *contained within* the intersection of its subsets' dense regions. Only evaluate inside that intersection — if it is empty, skip entirely."

**Slide content**

From Lemma 1 (applied to regions):
> R_θ(P)[s_sp] ⊆ ∩_{Q ⊂ P} R_θ(Q)[s_sp]

**Example** (s_sp fixed, time axis):

```
R_θ({A}) :  ████░░░░░████░░░░░░
            [10  30]  [50  70]

R_θ({B}) :  ░████░░░░░░████░░░░
            [15     40] [60   80]

∩ =         ░████░░░░░░████░░░░
Candidate:  [15 30]   [60 70]

R_θ({A,B}): must lie inside [15,30] ∪ [60,70]
```

**Two consequences**:
1. Only scan L_{A,B}(s_sp) within candidate intervals → fewer operations
2. If intersection = ∅ → **{A,B} cannot be dense → skip entirely** (no multiset built)

**This is exactly what Technique 2 implements** as the *candidate interval map* C(P, s_sp).

**Speaker notes**
- "Pattern pruning (S07) says *whether* to evaluate. Region pruning (this slide) says *where* to evaluate."
- Draw the timeline diagram on the slide — it is the most intuitive way to see the key idea.

---

### [S09] Background: 1D Apriori-Window (1.5 min)

**Heading**: Background — 1D Apriori-Window [Takahashi et al.]

**Key Message**:
> "1D Apriori-Window: count in a sliding window → collect dense start positions → output dense intervals. Time axis only."

**Slide content**

- **Window support**: `sup(P, l, W) = |{t ∈ occ(P) : l ≤ t ≤ l+W}|`
- **Dense start-point set**: `T_θ(P) = {l : sup(P,l,W) ≥ θ}`
- **Dense interval**: maximal contiguous component [a,b] → **[a, b+W]**

**Example**: occ={1,2,3,5,7,8}, W=3, θ=2 → T_θ={0,1} → dense interval **[0, 4]**

**Limitation**: time axis only

**Speaker notes**: "S06 definitions concretized in 1D. S07+S08 Apriori properties used to prune."

---

### [S10] Multi-Dimensional Transaction Data — Formal Definition (1 min)

**Heading**: Multi-Dimensional Transaction Data — From 1D to d-Dimensions

**Key Message**:
> "A d-dimensional transaction carries a coordinate vector (time + spatial axes) and an itemset. Discretize continuous coordinates into bins — that is the only pre-processing step."

**Slide content**

**Contrast with 1D**:

| | 1D | d-dimensional (this work) |
|---|---|---|
| Transaction | (t, items) | (b = (time, space₁,…,spaceₐ₋₁), items) |
| Window | [l, l+W] | [s₀,s₀+W₀] × [s₁,s₁+W₁] × … |
| Dense region | time interval | (spatial start point, time interval) pairs |

**Concrete example** (d=3: time × lat-bin × lon-bin):

```
(week=46, lat_bin=3, lon_bin=7) → {Beer, Chips}
(week=47, lat_bin=3, lon_bin=7) → {Beer, Chips}
(week=47, lat_bin=4, lon_bin=7) → {Beer}
   ↑ Pre-processing: discretize continuous coords into equal-width bins
```

**Types of spatial dimensions**:
- Geographic: latitude/longitude bins (retail, crime, earthquake)
- Categorical: store ID, borough (NYPD Crime)
- Physical: depth (USGS Earthquake — d=4)

**Speaker notes**: "Discretization is the only pre-processing. Bridge to EX-3 real data (S20)."

---

### [S11] Problem Definition: d-Dimensional Extension (1.5 min)

**Heading**: Problem Definition — d-Dimensional Dense Region

**Key Message**:
> "Extend to d-dim hyperrectangle. Anti-monotonicity carries over — Apriori pruning works at any dimension."

**Slide content**

- **d-dim support**: count of occurrences inside time window × spatial window
- **Dense region**: R_θ(P) = {(s_sp, [a_j, b_j+W₀])}

**Problem**: given D, W=(W₀,…,Wₐ₋₁), θ → enumerate R_θ(P) for every P

**Apriori monotonicity** (Lemma 1): Q ⊂ P ⟹ T_θ(P, s_sp) ⊆ T_θ(Q, s_sp)

**Figure**: `fig/fig2_1d_reduction` (left half)

**Speaker notes**: "S07+S08 Apriori properties hold for d-dim window support. S10 data structure formally defined."

---

### [S12] Technique 1: 1D Reduction per Spatial Start Point (1.5 min)

**Heading**: Technique 1 — 1D Reduction per Fixed Spatial Start Point

**Key Message**:
> "Fix a spatial start point → project timestamps into a multiset → 1D problem. Exact decomposition."

**Slide content**

- Fix s_sp → build multiset **L_P(s_sp)** (timestamps of P in the spatial window)
- d-dim problem = multiple 1D problems with **duplicate timestamps allowed**

**Cost**: one occurrence → ≤ W_sp = ∏(W_k+1) spatial start points → O(N_P · W_sp)

**Figure**: `fig/fig2_1d_reduction` (full)

---

### [S13] Technique 2: Apriori Pruning via Interval Map Intersection (1.5 min)

**Heading**: Technique 2 — Apriori Pruning via Interval Map Intersection

**Key Message**:
> "Candidate interval map = intersection of (k-1)-subset dense regions. Empty → skip. Non-empty → evaluate only inside."

**Slide content**

**Candidate interval map** (formalizes S08):
```
C(P, s_sp) = ∩ { R_θ(Q)[s_sp] : Q ∈ (k-1)-subsets of P }
```

**Two-level pruning** (S07 + S08 combined):
- C(P, s_sp) = ∅ for **all** s_sp → **skip** (no multiset built) ← pattern-level
- C(P, s_sp) ≠ ∅ → **evaluate only inside** candidate intervals ← region-level

**Speaker notes**: "S07 said *whether* to evaluate. S08 said *where* to evaluate. This slide implements both."

---

### [S14] Technique 3: Duplicate-Aware t-Stride (2 min)

**Heading**: Technique 3 — Duplicate-Aware t-Stride

**Key Message**:
> "Two-branch stride: bulk-output a guaranteed dense block, or gap-jump to the next useful position."

**Slide content**

**Problem**: in d≥2, duplicate timestamps in L → plain "+1 jump" fails

**Example**: L = {{1,2,2,3,3,8}}, W₀=3, θ=4

| State | Count c | Action |
|---|---|---|
| **Dense** c ≥ θ | 5 ≥ 4 | surplus c−θ=1 → bulk-output dense block [l, l_dense] |
| **Non-dense** c < θ | 1 < 4 | jump: l ← max(l+1, L[next]−W₀) |

- Dense: `l_dense = L[l_lo + (c−θ)]` — correctness by Lemma 2

**Figure**: `fig/fig3_t_stride`

---

### [S15] Full Algorithm & Complexity (1 min)

**Heading**: Full Algorithm — Multi-Dimensional Apriori-Window

**Key Message**:
> "Wrap the 1D solver over spatial start points; apply Apriori pruning at each level."

**Slide content**

```
for each item i:                    # k=1
    build L_i(s_sp); run t-stride → R_θ({i})
F_1 = { {i} : R_θ({i}) ≠ ∅ }

k = 2
while F_{k-1} ≠ ∅:
    for P in candidates(F_{k-1}):
        C(P, s_sp) = ∩ R_θ(Q)[s_sp]   # S13: interval map intersection
        if C = ∅ for all s_sp: skip     # S07: pattern pruning
        build L_P(s_sp)
        run t-stride restricted to C    # S08: region pruning
    k++
```

**Complexity**: O( Σ_{P∈F} (N_P·W_sp + Ñ_P log Ñ_P + I_P) )

---

### [S16] Experiments Overview (30 sec)

**Heading**: Experiments — Three Evaluations

**Key Message**:
> "Quality. Scalability. Interpretability."

| | Experiment | Goal |
|---|---|---|
| EX-1 | Synthetic data comparison | Quality gap vs. baselines |
| EX-2 | Scalability | Dependence on T / S / d / \|I\| |
| EX-3 | Real data (d=3–4) | Interpretability check |

**Environment**: Rust release build — Apple M3, 8-core, 24 GB RAM

---

### [S17] EX-1: Synthetic Data Design (1 min)

**Heading**: EX-1 — Synthetic Data with Four Embedded Dense Region Shapes

**Key Message**:
> "To test exact region recovery, we embed 4-shape GT in synthetic data — proposed outputs the exact solution by definition."

**Slide content**

**Setup**: T=100 × S=100 grid, 20 GT patterns, W=(20,5), θ=30

| Shape | Description |
|---|---|
| A Rectangle | Fixed-size orthogonal dense band |
| B Drift | Dense band shifts spatially over time |
| C Intermittent | Dense band appears and disappears |
| D Expanding | Dense region grows larger over time |

**Baselines**: EX-1-1 (F1): Colocation, STCP-Miner / EX-1-2 (Jaccard): LISA, MZoom, ST-DBSCAN

---

### [S18] EX-1: Results — Structural Mismatch (2 min)

**Heading**: EX-1 — Structural Mismatch, Not a Parameter Issue

**Key Message**:
> "F1 and Jaccard on synthetic data: proposed 1.00/1.00 vs. baselines ≤0.917/≤0.190 — structural gap, not a tuning issue."

**Slide content**

**EX-1-1 F1**: Proposed=1.00, STCP-Miner=0.917, Colocation=0.356

**EX-1-2 Jaccard**:

| Method | Jaccard | Root cause |
|---|---|---|
| **Proposed** | **1.00** | exact by definition |
| ST-DBSCAN | ≤ 0.190 | non-occurrence cells missed systematically |
| LISA | ≤ 0.10 | temporal information lost (full aggregation) |
| MZoom | lowest | product-block constraint → width-1 block |

**Figure**: `fig/fig_ex1_heatmap`

---

### [S19] EX-2: Scalability (1.5 min)

**Heading**: EX-2 — Linear Scaling up to 10⁸ Transactions

**Key Message**:
> "To test scalability, we vary N from 10⁴ to 10⁸ — linear scaling, 10⁸ in ~9 min."

**Slide content**

| Axis | Range | Result |
|---|---|---|
| T (time) | 10²–10⁵ | ≈ linear in N |
| S (space) | 10–10⁴ | ≈ linear |
| d: 2→4 | — | W_sp 25×; memory 1.35× only |
| \|I\|: 20→80 | — | sub-exponential (Apriori pruning) |

**Highlight**: N=10⁸ → **~9 min** ✓

**Figure**: `fig/fig_ex2_scalability`

---

### [S20] EX-3: Real Data — Interpretable Insights (1.5 min)

**Heading**: EX-3 — Real Data: Interpretable Insights across Domains

**Key Message**:
> "To verify interpretability, we apply to d=3–4 real data — domain-consistent patterns, no labeled GT needed."

**Slide content**

| Dataset | d | Axes (items) | Finding |
|---|---|---|---|
| Chicago Crime | 3 | week × lat-bin × lon-bin (crime types) | ASSAULT+BATTERY chronic hotspot in South/West Side; 3-way compound co-occurrence |
| NYPD Crime | 3 | week × borough × precinct (crime categories) | Felony + misdemeanor co-occur in specific borough × week windows |
| NYC 311 | 3 | week × community district × complaint type (service requests) | Noise + illegal parking cluster in residential districts |
| USGS Earthquake | 4 | week × lat-bin × lon-bin × depth-bin (magnitude class) | Shallow vs. mid-depth quakes split along depth axis |

---

### [S21] Conclusion (1.5 min)

**Heading**: Conclusion

**Key Message**:
> "Exact. Linear. Interpretable. Two open problems remain."

**Slide content**

**Contribution**: three techniques → exact enumeration of all (P, R(P)) pairs

| | Result |
|---|---|
| EX-1 | Proposed: F1=1.00, Jaccard=1.00 / Baselines: F1≤0.917, Jaccard≤0.190 |
| EX-2 | Linear N=10⁴–10⁸ (~9 min for 10⁸) |
| EX-3 | Interpretable insights on crime, complaints, earthquakes (d=3–4) |

**Limitations**:
- Grid discretization required (bin width and **W** affect results)
- O(N·W_sp) cost grows with W_sp and d
- Detection and description only (causal explanation out of scope)

**Future work**:
1. **Adaptive parameter selection** — auto-tune **W** and θ from local data statistics
2. **Faster construction** — O(1) window aggregation (prefix sums) + slice-differential spatial updates

---

### [S22] Q&A

**Heading**: Thank you — Questions?

**Key Message**:
> "What + When + Where — exactly, efficiently, interpretably."

**Content**: paper title, GitHub URL, contact

---

## Timeline

| Slide | Content | Time |
|---|---|---|
| S01 | Title | 0:30 |
| S02 | Motivation | 1:30 |
| S03 | Gap in existing methods | 2:00 |
| S04 | Contributions | 0:45 |
| S05 | **★NEW** What is multi-dim transaction data? | 1:00 |
| S06 | Dense Pattern & Dense Region (definitions) | 1:00 |
| S07 | Apriori Property — anti-monotonicity (pattern-level) | 1:00 |
| S08 | Apriori Property on Dense Regions (region intersection) | 1:00 |
| S09 | 1D background | 1:30 |
| S10 | Multi-dim transaction data (formal) | 1:00 |
| S11 | d-dim definition | 1:30 |
| S12 | Technique 1 | 1:30 |
| S13 | Technique 2 | 1:30 |
| S14 | Technique 3 | 2:00 |
| S15 | Full algorithm | 1:00 |
| S16 | Experiment overview | 0:30 |
| S17 | EX-1 design | 1:00 |
| S18 | EX-1 results | 2:00 |
| S19 | EX-2 scalability | 1:30 |
| S20 | EX-3 real data | 1:30 |
| S21 | Conclusion (summary + future work) | 1:30 |
| **Total** | | **~25 min** |

> **Trim to 17–18 min**:
> - Drop S15 (−1 min)
> - Merge S17+S18 (−1 min)
> - Compress S07+S08 into one "Apriori Property" slide (−1 min)
> - Compress S09+S10+S11 into two slides (−1.5 min)
> - Drop S05 or S10 — one visual intro suffices (−1 min)
> → **~19.5 min → 17–18 min**

---

## Logical Flow: S06 → S08 as a Three-Step Build-Up

```
S06  Dense Pattern & Region definitions
       ↓ "what is a dense region?"
S07  Apriori Property — PATTERN level
       "if P dense → all subsets dense"
       ↓ "does this extend to regions?"
S08  Apriori Property — REGION level
       "R_θ(P) ⊆ ∩ R_θ(subsets)"
       "only evaluate inside intersection"
       ↓ "how do we use this in practice?"
S13  Technique 2: interval map intersection
       "C(P, s_sp) = ∩ R_θ(Q)[s_sp]"
```

---

## Figure Reference

| Slide | File | Purpose |
|---|---|---|
| S02 | `fig/fig1_motivating.tex` | Motivating example |
| S11–12 | `fig/fig2_1d_reduction.tex` | d-dim → 1D reduction |
| S14 | `fig/fig3_t_stride.tex` | Two-branch stride |
| S18 | `fig/fig_ex1_heatmap.pdf` | EX-1 F1 / Jaccard heatmap |
| S19 | `fig/fig_ex2_scalability.pdf` | EX-2 scalability bar charts |
| S08 | (create new) | Timeline diagram: R(A) ∩ R(B) → candidate for {A,B} |
| S05 | (create new) | Left: 1D TD timeline / Right: 2D TD grid |

---

## Key Messages Quick Reference (rehearsal)

| Slide | Key Message |
|---|---|
| S01 | Answer both *what* and *where & when* — exactly, over any dimension. |
| S02 | Analysts need all four: What, When, Where, Action. No existing tool delivers all four. |
| S03 | Pattern mining lacks regions. Region detection lacks itemsets. Structural incompatibility. |
| S04 | Three techniques → exact enumeration of (P, R(P)) over any d-dimensional grid. |
| S05 | Transaction = coordinate vector + itemset. Add spatial axes → d-dim. Discretize once. |
| S06 | Frequent = global count. Dense = window count somewhere. Dense gives (P, R(P)) — what + when + where. |
| S07 | If any subset is not dense, the pattern cannot be dense — prune without evaluation. |
| S08 | R_θ(P) ⊆ ∩ R_θ(subsets). Only evaluate inside the intersection. Empty → skip entirely. |
| S09 | 1D Apriori-Window: count → dense intervals. Time axis only. |
| S10 | d-dim transaction = coordinate vector + itemset. Discretize → ready to mine. |
| S11 | Extend to d-dim hyperrectangle. Anti-monotonicity carries over. |
| S12 | Fix spatial start point → time multiset → 1D problem. |
| S13 | Candidate interval map = intersection of subset dense regions. Skip or restrict evaluation. |
| S14 | Two-branch stride: bulk-output dense block or gap-jump. |
| S15 | Wrap 1D solver + Apriori pruning per level. |
| S16 | Quality. Scalability. Interpretability. |
| S17 | To evaluate exact recovery, embed 4-shape GT in synthetic data → proposed outputs exact solution by definition. |
| S18 | Measuring F1 & Jaccard → proposed 1.00/1.00; baselines ≤0.917/≤0.190 — structural gap. |
| S19 | To evaluate scalability, vary N 10⁴–10⁸ → linear scaling; 10⁸ in ~9 min. |
| S20 | To verify interpretability, apply to d=3–4 real data → domain-consistent patterns without labeled GT. |
| S21 | Exact. Linear. Interpretable. Two open problems: adaptive params + faster construction. |
| S22 | What + When + Where — exactly, efficiently, interpretably. |
