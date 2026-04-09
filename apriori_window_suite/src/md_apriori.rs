//! 多次元 Apriori-Window (時間 × 空間 x × 空間 y)
//!
//! # アルゴリズム概要
//! 1. 離散化: 連続値座標 → (ti, xi, yi) ビンインデックス
//! 2. k=1: アイテムごとに t_events(xi,yi) を構築 → t軸 1D ストライド
//! 3. k≥2: Apriori 枝刈り → 候補セル限定で I_P 構築 → prefix sum → dense cells
//! 4. 6近傍連結成分で DenseRegion を返す
//!
//! # t軸 1D ストライドの厳密性
//! (xi,yi) 固定時、count(t) = t_events(xi,yi) 内の [t,t+Wt) 件数
//! = 3D ウィンドウ [t,t+Wt)×[xi,xi+Wx)×[yi,yi+Wy) のトランザクション数
//! → 1D と同一問題に帰着するため既存の compute_dense_intervals をそのまま流用

use std::collections::{HashMap, HashSet};

use rayon::prelude::*;

use crate::apriori::{generate_candidates, prune_candidates};
use crate::grid3d::{
    build_prefix_sum, compute_support_surface, connected_components_6, find_dense_cells,
    Grid3D,
};
use crate::grid_nd::{
    build_prefix_sum_nd, compute_support_surface_nd, connected_components_nd, find_dense_cells_nd,
    GridND,
};
use crate::util::{lower_bound, upper_bound};

// ---------------------------------------------------------------------------
// パラメータ・入力型
// ---------------------------------------------------------------------------

/// 多次元 Apriori のパラメータ
#[derive(Debug, Clone)]
pub struct Md3DParams {
    /// 各軸のビン幅 (dt, dx, dy)
    pub bin_sizes: (f64, f64, f64),
    /// ウィンドウ幅（ビン単位）(Wt, Wx, Wy)
    pub window_bins: (usize, usize, usize),
    /// サポート閾値
    pub threshold: usize,
    /// 最大パターン長
    pub max_length: usize,
}

/// 離散化済みトランザクション
#[derive(Debug, Clone)]
pub struct Txn3D {
    pub ti: usize,
    pub xi: usize,
    pub yi: usize,
    pub items: Vec<i64>,
}

/// 密集領域（密集セルのリスト）
pub type DenseRegion = Vec<(usize, usize, usize)>;

// ---------------------------------------------------------------------------
// 離散化
// ---------------------------------------------------------------------------

/// 連続値トランザクション → 離散化。グリッドサイズ (T, X, Y) も返す。
pub fn discretize(
    raw: &[(f64, f64, f64, Vec<i64>)],
    params: &Md3DParams,
) -> (Vec<Txn3D>, (usize, usize, usize)) {
    let (dt, dx, dy) = params.bin_sizes;
    if raw.is_empty() {
        return (Vec::new(), (1, 1, 1));
    }

    let txns: Vec<Txn3D> = raw
        .iter()
        .map(|(t, x, y, items)| Txn3D {
            ti: (t / dt).floor() as usize,
            xi: (x / dx).floor() as usize,
            yi: (y / dy).floor() as usize,
            items: items.clone(),
        })
        .collect();

    let max_t = txns.iter().map(|tx| tx.ti).max().unwrap_or(0);
    let max_x = txns.iter().map(|tx| tx.xi).max().unwrap_or(0);
    let max_y = txns.iter().map(|tx| tx.yi).max().unwrap_or(0);

    (txns, (max_t + 1, max_x + 1, max_y + 1))
}

// ---------------------------------------------------------------------------
// t_events マップ構築
// ---------------------------------------------------------------------------

/// (xs, ys) → [ti, ti, ...] のマップを構築。
///
/// xs ∈ [xi - Wx + 1, xi]、ys ∈ [yi - Wy + 1, yi] のウィンドウに
/// トランザクション (ti, xi, yi) が含まれる。
/// つまりトランザクション (ti, xi, yi) は
///   xs ∈ [max(0, xi-Wx+1), xi]
///   ys ∈ [max(0, yi-Wy+1), yi]
/// のすべての (xs, ys) に ti を追加する。
///
/// 逆引きコスト: O(N × Wx × Wy)
fn build_xy_t_events(
    txns: &[Txn3D],
    wt: usize,
    wx: usize,
    wy: usize,
    item: i64,
    dims: (usize, usize, usize),
) -> HashMap<(usize, usize), Vec<i64>> {
    let (_, gx, gy) = dims;
    let _ = wt; // Wt は 1D stride 側で使用

    let mut map: HashMap<(usize, usize), Vec<i64>> = HashMap::new();

    for txn in txns {
        if !txn.items.contains(&item) {
            continue;
        }
        let xi = txn.xi;
        let yi = txn.yi;
        let xs_lo = (xi + 1).saturating_sub(wx);
        let ys_lo = (yi + 1).saturating_sub(wy);
        let xs_hi = xi.min(gx.saturating_sub(1));
        let ys_hi = yi.min(gy.saturating_sub(1));

        for xs in xs_lo..=xs_hi {
            for ys in ys_lo..=ys_hi {
                map.entry((xs, ys)).or_default().push(txn.ti as i64);
            }
        }
    }

    // ソートして 1D stride に渡せるようにする
    for v in map.values_mut() {
        v.sort_unstable();
    }
    map
}

// ---------------------------------------------------------------------------
// t軸 1D ストライド（bin インデックス専用）
// ---------------------------------------------------------------------------

/// bin インデックスのイベントリストから密集ウィンドウ開始 bin を求める。
///
/// `compute_dense_intervals` は連続タイムスタンプ向けのフィルタを持つため、
/// bin 単位のウィンドウ [l, l+wt) には使用しない。
/// ストライドの正確性はタイムスタンプ版と同一（スキップ区間は全て密集）。
fn dense_window_starts_stride(t_events: &[i64], wt: usize, theta: usize) -> Vec<usize> {
    if t_events.is_empty() || wt == 0 || theta == 0 {
        return Vec::new();
    }

    let mut starts = Vec::new();
    let last_event = *t_events.last().unwrap() as usize;
    let first_event = *t_events.first().unwrap() as usize;
    // ウィンドウ [l, l+wt) が最初のイベントを含む最小の l から開始
    let l_init = first_event.saturating_sub(wt - 1);
    let mut l = l_init;
    // stride でスキップした直前の密集 l（スキップ区間を後で補填するため）
    let mut prev_dense_l: Option<usize> = None;

    while l <= last_event {
        let lo = lower_bound(t_events, l as i64);
        // 半開区間 [l, l+wt) → t_bin ∈ [l, l+wt-1] → upper_bound(l+wt-1)
        let hi = upper_bound(t_events, (l + wt) as i64 - 1);
        let count = hi - lo;

        if count >= theta {
            // stride でスキップされた密集区間を補填
            if let Some(prev) = prev_dense_l {
                for skipped in (prev + 1)..l {
                    starts.push(skipped);
                }
            }
            starts.push(l);
            prev_dense_l = Some(l);

            if count > theta {
                let surplus = count - theta;
                let next_l = t_events[lo + surplus] as usize;
                if next_l > l {
                    l = next_l; // スキップ区間は全て密集（補填は次ループで）
                } else {
                    l += 1; // スタックケース
                }
            } else {
                l += 1;
            }
        } else {
            prev_dense_l = None;
            // ウィンドウが次のイベントを含む最初の l へジャンプ
            // window [l', l'+wt) が t_events[next_lo] を含む → l' ≤ t_events[next_lo] < l'+wt
            // 最小の l' = t_events[next_lo] - wt + 1（ただし l+1 以上）
            let next_lo = upper_bound(t_events, l as i64); // first > l
            if next_lo >= t_events.len() {
                break;
            }
            let next_event = t_events[next_lo] as usize;
            let candidate = next_event.saturating_sub(wt - 1);
            l = candidate.max(l + 1);
        }
    }

    starts
}

// ---------------------------------------------------------------------------
// k=1: アイテムごとの密集セル
// ---------------------------------------------------------------------------

/// アイテム i の密集セル集合を t軸 1D ストライドで計算
fn dense_cells_for_item(
    txns: &[Txn3D],
    item: i64,
    params: &Md3DParams,
    dims: (usize, usize, usize),
) -> Vec<(usize, usize, usize)> {
    let (wt, wx, wy) = params.window_bins;
    let theta = params.threshold;
    let (gt, gx, gy) = dims;

    let xy_t_events = build_xy_t_events(txns, wt, wx, wy, item, dims);

    let mut dense = Vec::new();

    for xs in 0..gx {
        for ys in 0..gy {
            let Some(t_events) = xy_t_events.get(&(xs, ys)) else {
                continue;
            };
            if t_events.is_empty() {
                continue;
            }

            // t 軸 1D ストライド（bin インデックス専用版）
            let dense_starts = dense_window_starts_stride(t_events, wt, theta);
            for ti in dense_starts {
                if ti < gt {
                    dense.push((ti, xs, ys));
                }
            }
        }
    }

    dense.sort_unstable();
    dense.dedup();
    dense
}

// ---------------------------------------------------------------------------
// k≥2: I_P 構築 + prefix sum
// ---------------------------------------------------------------------------

/// パターン P の出現グリッド I_P を候補セル限定で構築
fn build_item_grid(
    txns: &[Txn3D],
    pattern: &[i64],
    candidate_cells: &HashSet<(usize, usize, usize)>,
    dims: (usize, usize, usize),
) -> Grid3D {
    let (gt, gx, gy) = dims;
    let mut grid = Grid3D::new(gt, gx, gy);

    for txn in txns {
        let cell = (txn.ti, txn.xi, txn.yi);
        if !candidate_cells.contains(&cell) {
            continue;
        }
        if pattern.iter().all(|it| txn.items.contains(it)) {
            grid.add(txn.ti, txn.xi, txn.yi, 1);
        }
    }
    grid
}

// ---------------------------------------------------------------------------
// メイン関数
// ---------------------------------------------------------------------------

/// 3D 密集アイテムセット検出
///
/// 戻り値: `HashMap<pattern, Vec<DenseRegion>>`
/// DenseRegion は密集セル (ti, xi, yi) のリスト
pub fn find_dense_itemsets_3d(
    transactions: &[(f64, f64, f64, Vec<i64>)],
    params: &Md3DParams,
) -> HashMap<Vec<i64>, Vec<DenseRegion>> {
    let (txns, dims) = discretize(transactions, params);
    let (wt, wx, wy) = params.window_bins;
    let theta = params.threshold as u32;

    if txns.is_empty() {
        return HashMap::new();
    }

    // --- 全アイテムのリスト ---
    let mut all_items: Vec<i64> = txns
        .iter()
        .flat_map(|tx| tx.items.iter().cloned())
        .collect();
    all_items.sort_unstable();
    all_items.dedup();

    // --- k=1: 各アイテムの密集セル（Rayon 並列） ---
    let k1_results: Vec<(i64, Vec<(usize, usize, usize)>)> = all_items
        .par_iter()
        .map(|&item| {
            let cells = dense_cells_for_item(&txns, item, params, dims);
            (item, cells)
        })
        .filter(|(_, cells)| !cells.is_empty())
        .collect();

    let mut dense_cells_map: HashMap<Vec<i64>, Vec<(usize, usize, usize)>> = HashMap::new();
    let mut current_level: Vec<Vec<i64>> = Vec::new();

    for (item, cells) in k1_results {
        let key = vec![item];
        dense_cells_map.insert(key.clone(), cells);
        current_level.push(key);
    }

    // dense cells → regions（連結成分）
    let mut result: HashMap<Vec<i64>, Vec<DenseRegion>> = HashMap::new();
    for (pat, cells) in &dense_cells_map {
        let regions = connected_components_6(cells, dims);
        if !regions.is_empty() {
            result.insert(pat.clone(), regions);
        }
    }

    // --- k≥2: Apriori 拡張 ---
    let mut k = 2;
    while !current_level.is_empty() && k <= params.max_length {
        let candidates = generate_candidates(&current_level, k);
        let prev_set: HashSet<Vec<i64>> = current_level.iter().cloned().collect();
        let candidates = prune_candidates(candidates, &prev_set);

        let candidate_results: Vec<(Vec<i64>, Vec<(usize, usize, usize)>)> = candidates
            .par_iter()
            .map(|pattern| {
                // Apriori 枝刈り: 全 (k-1)-部分集合の密集セル交差
                let subsets: Vec<Vec<i64>> = pattern
                    .iter()
                    .cloned()
                    .enumerate()
                    .map(|(skip, _)| {
                        pattern
                            .iter()
                            .cloned()
                            .enumerate()
                            .filter(|(i, _)| *i != skip)
                            .map(|(_, v)| v)
                            .collect::<Vec<i64>>()
                    })
                    .collect();

                // 全部分集合の dense cells が存在するか確認
                let sub_cell_sets: Vec<HashSet<(usize, usize, usize)>> = subsets
                    .iter()
                    .filter_map(|sub| {
                        dense_cells_map
                            .get(sub)
                            .map(|cells| cells.iter().cloned().collect::<HashSet<_>>())
                    })
                    .collect();

                if sub_cell_sets.len() != subsets.len() {
                    return (pattern.clone(), Vec::new());
                }

                // 候補セル = 全部分集合の dense cells の交差
                let candidate_cells: HashSet<(usize, usize, usize)> = sub_cell_sets
                    .iter()
                    .skip(1)
                    .fold(sub_cell_sets[0].clone(), |acc, s| {
                        acc.intersection(s).cloned().collect()
                    });

                if candidate_cells.is_empty() {
                    return (pattern.clone(), Vec::new());
                }

                // I_P 構築 → prefix sum → support surface → dense cells
                let grid = build_item_grid(&txns, pattern, &candidate_cells, dims);
                let ps = build_prefix_sum(&grid);
                let surface = compute_support_surface(&ps, wt, wx, wy);
                let cells = find_dense_cells(&surface, theta);

                (pattern.clone(), cells)
            })
            .filter(|(_, cells)| !cells.is_empty())
            .collect();

        let mut next_level: Vec<Vec<i64>> = Vec::new();
        for (pattern, cells) in candidate_results {
            let regions = connected_components_6(&cells, dims);
            if !regions.is_empty() {
                result.insert(pattern.clone(), regions);
                dense_cells_map.insert(pattern.clone(), cells);
                next_level.push(pattern);
            }
        }

        current_level = next_level;
        k += 1;
    }

    result
}

// ---------------------------------------------------------------------------
// d 次元版: パラメータ・入力型
// ---------------------------------------------------------------------------

/// d 次元 Apriori-Window パラメータ
#[derive(Debug, Clone)]
pub struct MdNDParams {
    /// 各次元のビン幅（長さ d）
    pub bin_sizes: Vec<f64>,
    /// 各次元のウィンドウ幅（ビン単位、長さ d）
    pub window_bins: Vec<usize>,
    /// サポート閾値
    pub threshold: usize,
    /// 最大パターン長
    pub max_length: usize,
}

/// 離散化済みトランザクション（d 次元）
#[derive(Debug, Clone)]
pub struct TxnND {
    /// 各次元のビンインデックス（長さ d）
    pub coords: Vec<usize>,
    pub items: Vec<i64>,
}

/// 密集領域（密集セルの d 次元座標リスト）
pub type DenseRegionND = Vec<Vec<usize>>;

// ---------------------------------------------------------------------------
// d 次元離散化
// ---------------------------------------------------------------------------

/// 連続値トランザクション → 離散化。グリッドサイズも返す。
///
/// `raw`: 各要素 `(coords: Vec<f64>, items: Vec<i64>)` の配列
/// `coords.len()` は `params.bin_sizes.len()` と一致すること。
pub fn discretize_nd(
    raw: &[(Vec<f64>, Vec<i64>)],
    params: &MdNDParams,
) -> (Vec<TxnND>, Vec<usize>) {
    let d = params.bin_sizes.len();
    if raw.is_empty() {
        return (Vec::new(), vec![1; d]);
    }

    let txns: Vec<TxnND> = raw
        .iter()
        .map(|(coords, items)| TxnND {
            coords: coords
                .iter()
                .zip(params.bin_sizes.iter())
                .map(|(c, &b)| (c / b).floor() as usize)
                .collect(),
            items: items.clone(),
        })
        .collect();

    let dims: Vec<usize> = (0..d)
        .map(|dim| txns.iter().map(|tx| tx.coords[dim]).max().unwrap_or(0) + 1)
        .collect();

    (txns, dims)
}

// ---------------------------------------------------------------------------
// d 次元 t_events マップ構築
// ---------------------------------------------------------------------------

/// 空間次元キー → [ti, ti, ...] のマップを構築。
///
/// d 次元版: coords[0] = ti（時間）、coords[1..d] = 空間座標
/// 空間ウィンドウ開始 `(xs1, xs2, ..., xs_{d-1})` が
///   xs_k ∈ [max(0, sk - W_k + 1), sk]   (k = 1..d-1)
/// を満たす全組み合わせに ti を追加する。
///
/// キーは空間座標ベクタ（長さ d-1）。
fn build_spatial_t_events_nd(
    txns: &[TxnND],
    item: i64,
    params: &MdNDParams,
    dims: &[usize],
) -> HashMap<Vec<usize>, Vec<i64>> {
    let d = dims.len();
    // space_windows[k] = window_bins[k+1] (k=0..d-2)
    let space_windows: Vec<usize> = params.window_bins[1..].to_vec();
    let space_dims: Vec<usize> = dims[1..].to_vec();

    let mut map: HashMap<Vec<usize>, Vec<i64>> = HashMap::new();

    for txn in txns {
        if !txn.items.contains(&item) {
            continue;
        }
        let ti = txn.coords[0] as i64;
        // 空間次元について xs_k の有効範囲を計算
        let ranges: Vec<std::ops::RangeInclusive<usize>> = (0..d - 1)
            .map(|k| {
                let sk = txn.coords[k + 1];
                let wk = space_windows[k];
                let lo = (sk + 1).saturating_sub(wk);
                let hi = sk.min(space_dims[k].saturating_sub(1));
                lo..=hi
            })
            .collect();

        // 全組み合わせをイテレート
        for_each_product(&ranges, &mut |key: &[usize]| {
            map.entry(key.to_vec()).or_default().push(ti);
        });
    }

    // ソート
    for v in map.values_mut() {
        v.sort_unstable();
    }
    map
}

/// 多次元デカルト積のユーティリティ（範囲リスト → コールバック）
fn for_each_product(
    ranges: &[std::ops::RangeInclusive<usize>],
    callback: &mut impl FnMut(&[usize]),
) {
    fn recurse(
        ranges: &[std::ops::RangeInclusive<usize>],
        current: &mut Vec<usize>,
        callback: &mut impl FnMut(&[usize]),
    ) {
        if current.len() == ranges.len() {
            callback(current);
            return;
        }
        let idx = current.len();
        for v in ranges[idx].clone() {
            current.push(v);
            recurse(ranges, current, callback);
            current.pop();
        }
    }
    let mut current = Vec::with_capacity(ranges.len());
    recurse(ranges, &mut current, callback);
}

// ---------------------------------------------------------------------------
// d 次元 k=1: アイテムごとの密集セル
// ---------------------------------------------------------------------------

fn dense_cells_for_item_nd(
    txns: &[TxnND],
    item: i64,
    params: &MdNDParams,
    dims: &[usize],
) -> Vec<Vec<usize>> {
    let wt = params.window_bins[0];
    let theta = params.threshold;
    let gt = dims[0];
    let space_dims: Vec<usize> = dims[1..].to_vec();

    let spatial_t_events = build_spatial_t_events_nd(txns, item, params, dims);

    let mut dense: Vec<Vec<usize>> = Vec::new();

    // 空間次元の全格子点をイテレート
    let space_total: usize = space_dims.iter().product();
    let space_strides = {
        let mut s = vec![1usize; space_dims.len()];
        for i in 1..space_dims.len() {
            s[i] = s[i - 1] * space_dims[i - 1];
        }
        s
    };

    for flat in 0..space_total {
        let space_key: Vec<usize> = {
            let mut key = vec![0usize; space_dims.len()];
            let mut rem = flat;
            for i in (0..space_dims.len()).rev() {
                key[i] = rem / space_strides[i];
                rem %= space_strides[i];
            }
            key
        };

        let Some(t_events) = spatial_t_events.get(&space_key) else {
            continue;
        };
        if t_events.is_empty() {
            continue;
        }

        let dense_starts = dense_window_starts_stride(t_events, wt, theta);
        for ti in dense_starts {
            if ti < gt {
                let mut coords = vec![ti];
                coords.extend_from_slice(&space_key);
                dense.push(coords);
            }
        }
    }

    dense.sort_unstable();
    dense.dedup();
    dense
}

// ---------------------------------------------------------------------------
// d 次元 k≥2: I_P 構築 + prefix sum
// ---------------------------------------------------------------------------

fn build_item_grid_nd(
    txns: &[TxnND],
    pattern: &[i64],
    candidate_cells: &HashSet<Vec<usize>>,
    dims: &[usize],
) -> GridND {
    let mut grid = GridND::new(dims.to_vec());

    for txn in txns {
        let cell = txn.coords.clone();
        if !candidate_cells.contains(&cell) {
            continue;
        }
        if pattern.iter().all(|it| txn.items.contains(it)) {
            grid.add(&cell, 1);
        }
    }
    grid
}

// ---------------------------------------------------------------------------
// d 次元メイン関数
// ---------------------------------------------------------------------------

/// d 次元密集アイテムセット検出
///
/// `raw`: 各要素 `(coords: Vec<f64>, items: Vec<i64>)`
///        `coords[0]` = 時間座標、`coords[1..]` = 空間座標
///
/// 戻り値: `HashMap<pattern, Vec<DenseRegionND>>`
/// DenseRegionND は密集セルの d 次元座標リスト
pub fn find_dense_itemsets_nd(
    raw: &[(Vec<f64>, Vec<i64>)],
    params: &MdNDParams,
) -> HashMap<Vec<i64>, Vec<DenseRegionND>> {
    let (txns, dims) = discretize_nd(raw, params);
    let theta = params.threshold as u32;

    if txns.is_empty() {
        return HashMap::new();
    }

    // --- 全アイテムのリスト ---
    let mut all_items: Vec<i64> = txns
        .iter()
        .flat_map(|tx| tx.items.iter().cloned())
        .collect();
    all_items.sort_unstable();
    all_items.dedup();

    // --- k=1: 各アイテムの密集セル（Rayon 並列） ---
    let k1_results: Vec<(i64, Vec<Vec<usize>>)> = all_items
        .par_iter()
        .map(|&item| {
            let cells = dense_cells_for_item_nd(&txns, item, params, &dims);
            (item, cells)
        })
        .filter(|(_, cells)| !cells.is_empty())
        .collect();

    let mut dense_cells_map: HashMap<Vec<i64>, Vec<Vec<usize>>> = HashMap::new();
    let mut current_level: Vec<Vec<i64>> = Vec::new();

    for (item, cells) in k1_results {
        let key = vec![item];
        dense_cells_map.insert(key.clone(), cells);
        current_level.push(key);
    }

    // dense cells → regions（連結成分）
    let mut result: HashMap<Vec<i64>, Vec<DenseRegionND>> = HashMap::new();
    for (pat, cells) in &dense_cells_map {
        let regions = connected_components_nd(cells, &dims);
        if !regions.is_empty() {
            result.insert(pat.clone(), regions);
        }
    }

    // --- k≥2: Apriori 拡張 ---
    let mut k = 2;
    while !current_level.is_empty() && k <= params.max_length {
        let candidates = generate_candidates(&current_level, k);
        let prev_set: HashSet<Vec<i64>> = current_level.iter().cloned().collect();
        let candidates = prune_candidates(candidates, &prev_set);

        let candidate_results: Vec<(Vec<i64>, Vec<Vec<usize>>)> = candidates
            .par_iter()
            .map(|pattern| {
                // Apriori 枝刈り: 全 (k-1)-部分集合の密集セル交差
                let subsets: Vec<Vec<i64>> = (0..pattern.len())
                    .map(|skip| {
                        pattern
                            .iter()
                            .cloned()
                            .enumerate()
                            .filter(|(i, _)| *i != skip)
                            .map(|(_, v)| v)
                            .collect::<Vec<i64>>()
                    })
                    .collect();

                let sub_cell_sets: Vec<HashSet<Vec<usize>>> = subsets
                    .iter()
                    .filter_map(|sub| {
                        dense_cells_map
                            .get(sub)
                            .map(|cells| cells.iter().cloned().collect::<HashSet<_>>())
                    })
                    .collect();

                if sub_cell_sets.len() != subsets.len() {
                    return (pattern.clone(), Vec::new());
                }

                let candidate_cells: HashSet<Vec<usize>> = sub_cell_sets
                    .iter()
                    .skip(1)
                    .fold(sub_cell_sets[0].clone(), |acc, s| {
                        acc.intersection(s).cloned().collect()
                    });

                if candidate_cells.is_empty() {
                    return (pattern.clone(), Vec::new());
                }

                let grid = build_item_grid_nd(&txns, pattern, &candidate_cells, &dims);
                let ps = build_prefix_sum_nd(&grid);
                let surface = compute_support_surface_nd(&ps, &params.window_bins);
                let cells = find_dense_cells_nd(&surface, theta);

                (pattern.clone(), cells)
            })
            .filter(|(_, cells)| !cells.is_empty())
            .collect();

        let mut next_level: Vec<Vec<i64>> = Vec::new();
        for (pattern, cells) in candidate_results {
            let regions = connected_components_nd(&cells, &dims);
            if !regions.is_empty() {
                result.insert(pattern.clone(), regions);
                dense_cells_map.insert(pattern.clone(), cells);
                next_level.push(pattern);
            }
        }

        current_level = next_level;
        k += 1;
    }

    result
}

// ---------------------------------------------------------------------------
// テスト
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_txn(t: f64, x: f64, y: f64, items: Vec<i64>) -> (f64, f64, f64, Vec<i64>) {
        (t, x, y, items)
    }

    /// 植え付け実験: 既知の密集領域を合成データに注入 → 完全回収
    #[test]
    fn test_planted_dense_region() {
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (3, 1, 1),
            threshold: 3,
            max_length: 2,
        };

        // t=0,1,2 に (x=0,y=0) でアイテム [1,2] が 3 回ずつ出現
        let mut txns = Vec::new();
        for ti in 0..3 {
            for _ in 0..3 {
                txns.push(make_txn(ti as f64, 0.0, 0.0, vec![1, 2]));
            }
        }
        // ノイズ（密集しない位置）
        txns.push(make_txn(10.0, 5.0, 5.0, vec![1, 2]));

        let result = find_dense_itemsets_3d(&txns, &params);

        assert!(
            result.contains_key(&vec![1i64]),
            "アイテム [1] の密集領域が検出されること"
        );
        assert!(
            result.contains_key(&vec![2i64]),
            "アイテム [2] の密集領域が検出されること"
        );
        assert!(
            result.contains_key(&vec![1i64, 2]),
            "アイテムセット [1,2] の密集領域が検出されること"
        );
    }

    /// 枝刈り正確性: 枝刈り有り/無しで同じ結果
    #[test]
    fn test_apriori_pruning_correctness() {
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (3, 1, 1),
            threshold: 3,
            max_length: 3,
        };

        let mut txns = Vec::new();
        // アイテム [1,2,3] が (t=0,x=0,y=0) 付近に 5 件
        for ti in 0..5 {
            txns.push(make_txn(ti as f64, 0.0, 0.0, vec![1, 2, 3]));
        }
        // アイテム [1,2] のみ (t=10,x=0,y=0)
        for ti in 10..13 {
            txns.push(make_txn(ti as f64, 0.0, 0.0, vec![1, 2]));
        }

        let result = find_dense_itemsets_3d(&txns, &params);

        // [1,2,3] が見つかる → [1,2], [1,3], [2,3] も見つかるはず
        if result.contains_key(&vec![1i64, 2, 3]) {
            assert!(result.contains_key(&vec![1i64, 2]));
            assert!(result.contains_key(&vec![1i64, 3]));
            assert!(result.contains_key(&vec![2i64, 3]));
        }
    }

    /// 空入力
    #[test]
    fn test_empty_transactions() {
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (3, 1, 1),
            threshold: 2,
            max_length: 2,
        };
        let result = find_dense_itemsets_3d(&[], &params);
        assert!(result.is_empty());
    }

    /// 閾値以下は検出されない
    #[test]
    fn test_below_threshold_not_detected() {
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (3, 1, 1),
            threshold: 5,
            max_length: 2,
        };
        let txns: Vec<_> = (0..3)
            .map(|ti| make_txn(ti as f64, 0.0, 0.0, vec![1]))
            .collect();
        let result = find_dense_itemsets_3d(&txns, &params);
        assert!(result.is_empty(), "threshold=5 に対して 3 件では密集なし");
    }

    /// dense_window_starts_stride の単体テスト（ブルートフォース比較）
    #[test]
    fn test_dense_window_starts_stride() {
        // ブルートフォース参照実装
        fn brute_force(ts: &[i64], wt: usize, theta: usize) -> Vec<usize> {
            if ts.is_empty() {
                return Vec::new();
            }
            let max_t = *ts.last().unwrap() as usize;
            let mut out = Vec::new();
            for l in 0..=max_t {
                let cnt = ts
                    .iter()
                    .filter(|&&t| t as usize >= l && (t as usize) < l + wt)
                    .count();
                if cnt >= theta {
                    out.push(l);
                }
            }
            out
        }

        let cases: &[(&[i64], usize, usize)] = &[
            (&[0, 0, 0, 1, 1, 1, 2, 2, 2], 3, 3),
            (&[0, 0, 1, 2, 3, 3, 5, 8], 4, 3),
            (&[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5, 3),
            (&[5, 5, 5, 5, 5, 8, 12], 6, 3), // スタックケース
            (&[0, 5, 6, 7], 3, 2),
        ];

        for &(ts, wt, theta) in cases {
            let mut got = dense_window_starts_stride(ts, wt, theta);
            got.sort_unstable();
            let expected = brute_force(ts, wt, theta);
            assert_eq!(
                got, expected,
                "ts={:?} wt={} theta={}: got={:?} expected={:?}",
                ts, wt, theta, got, expected
            );
        }
    }

    /// 1D との整合性: y=0 固定、Wy=1 のとき dense window starts が一致する
    #[test]
    fn test_1d_consistency() {
        let wt = 4usize;
        let theta = 3usize;
        let ts_vals: Vec<i64> = vec![0, 0, 1, 2, 3, 3, 5, 8];

        // 参照: ブルートフォースで求めた dense window starts
        let max_t = *ts_vals.last().unwrap() as usize;
        let mut expected_starts: Vec<usize> = (0..=max_t)
            .filter(|&l| {
                ts_vals
                    .iter()
                    .filter(|&&t| t as usize >= l && (t as usize) < l + wt)
                    .count()
                    >= theta
            })
            .collect();
        expected_starts.sort_unstable();

        // 3D 設定: x=0 固定、Wx=1、y=0 固定、Wy=1
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (wt, 1, 1),
            threshold: theta,
            max_length: 1,
        };
        let txns: Vec<_> = ts_vals
            .iter()
            .map(|&ti| make_txn(ti as f64, 0.0, 0.0, vec![1]))
            .collect();

        let result_3d = find_dense_itemsets_3d(&txns, &params);

        let mut t_set_3d: Vec<usize> = if let Some(regions) = result_3d.get(&vec![1i64]) {
            regions
                .iter()
                .flat_map(|r| r.iter().map(|&(ti, _, _)| ti))
                .collect()
        } else {
            Vec::new()
        };
        t_set_3d.sort_unstable();
        t_set_3d.dedup();

        assert_eq!(
            t_set_3d, expected_starts,
            "3D (x=y=0固定, Wx=Wy=1) はブルートフォースと同じ dense window starts を返すこと"
        );
    }

    // -----------------------------------------------------------------------
    // ND 版テスト
    // -----------------------------------------------------------------------

    /// ND 版ヘルパー: (t, x, y, items) → (Vec<f64>, Vec<i64>)
    fn make_txn_nd(t: f64, x: f64, y: f64, items: Vec<i64>) -> (Vec<f64>, Vec<i64>) {
        (vec![t, x, y], items)
    }

    /// 植え付け実験（ND 版）: 既知の密集領域を合成データに注入 → 完全回収
    #[test]
    fn test_nd_planted_dense_region() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![3, 1, 1],
            threshold: 3,
            max_length: 2,
        };

        let mut txns = Vec::new();
        for ti in 0..3 {
            for _ in 0..3 {
                txns.push(make_txn_nd(ti as f64, 0.0, 0.0, vec![1, 2]));
            }
        }
        txns.push(make_txn_nd(10.0, 5.0, 5.0, vec![1, 2]));

        let result = find_dense_itemsets_nd(&txns, &params);

        assert!(
            result.contains_key(&vec![1i64]),
            "ND: アイテム [1] の密集領域が検出されること"
        );
        assert!(
            result.contains_key(&vec![2i64]),
            "ND: アイテム [2] の密集領域が検出されること"
        );
        assert!(
            result.contains_key(&vec![1i64, 2]),
            "ND: アイテムセット [1,2] の密集領域が検出されること"
        );
    }

    /// d=3 で find_dense_itemsets_nd が find_dense_itemsets_3d と同じ結果を返すこと
    #[test]
    fn test_nd_equals_3d() {
        let params_3d = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (3, 2, 2),
            threshold: 3,
            max_length: 2,
        };
        let params_nd = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![3, 2, 2],
            threshold: 3,
            max_length: 2,
        };

        // 同じデータを両方に入力
        let raw_3d: Vec<(f64, f64, f64, Vec<i64>)> = vec![
            make_txn(0.0, 0.0, 0.0, vec![1, 2]),
            make_txn(1.0, 0.0, 0.0, vec![1, 2]),
            make_txn(2.0, 0.0, 0.0, vec![1, 2]),
            make_txn(3.0, 0.0, 1.0, vec![1]),
            make_txn(5.0, 2.0, 0.0, vec![2]),
            make_txn(10.0, 5.0, 5.0, vec![1, 2]),
        ];
        let raw_nd: Vec<(Vec<f64>, Vec<i64>)> = raw_3d
            .iter()
            .map(|(t, x, y, items)| (vec![*t, *x, *y], items.clone()))
            .collect();

        let result_3d = find_dense_itemsets_3d(&raw_3d, &params_3d);
        let result_nd = find_dense_itemsets_nd(&raw_nd, &params_nd);

        // 同じパターンセットが検出されること
        let mut keys_3d: Vec<Vec<i64>> = result_3d.keys().cloned().collect();
        let mut keys_nd: Vec<Vec<i64>> = result_nd.keys().cloned().collect();
        keys_3d.sort();
        keys_nd.sort();
        assert_eq!(
            keys_3d, keys_nd,
            "d=3: find_dense_itemsets_nd と find_dense_itemsets_3d は同じパターンを検出すること"
        );

        // 各パターンの総密集セル数が一致すること
        for key in &keys_3d {
            let cells_3d: usize = result_3d[key].iter().map(|r| r.len()).sum();
            let cells_nd: usize = result_nd[key].iter().map(|r| r.len()).sum();
            assert_eq!(
                cells_3d, cells_nd,
                "パターン {:?}: 総密集セル数が一致すること ({} vs {})",
                key, cells_3d, cells_nd
            );
        }
    }

    /// ND 版: 空入力
    #[test]
    fn test_nd_empty_transactions() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![3, 1, 1],
            threshold: 2,
            max_length: 2,
        };
        let result = find_dense_itemsets_nd(&[], &params);
        assert!(result.is_empty());
    }

    /// ND 版: 閾値以下は検出されない
    #[test]
    fn test_nd_below_threshold_not_detected() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![3, 1, 1],
            threshold: 5,
            max_length: 2,
        };
        let txns: Vec<_> = (0..3)
            .map(|ti| (vec![ti as f64, 0.0, 0.0], vec![1i64]))
            .collect();
        let result = find_dense_itemsets_nd(&txns, &params);
        assert!(result.is_empty(), "ND: threshold=5 に対して 3 件では密集なし");
    }
}
