//! d 次元グリッド・接頭辞和・連結成分
//!
//! # 設計
//! - `GridND`: フラット配列による d 次元グリッド（row-major, strides[0]=1）
//! - `PrefixSumND`: 各次元 +1 パディングの接頭辞和
//! - `connected_components_nd`: 2d-近傍（各次元 ±1）Union-Find

use std::collections::HashMap;

// ---------------------------------------------------------------------------
// GridND
// ---------------------------------------------------------------------------

/// フラット配列による d 次元グリッド
#[derive(Debug, Clone)]
pub struct GridND {
    pub data: Vec<u32>,
    pub dims: Vec<usize>,
    strides: Vec<usize>,
}

impl GridND {
    /// 全ゼロで初期化。dims[i] は第 i 次元のサイズ。
    pub fn new(dims: Vec<usize>) -> Self {
        let total: usize = dims.iter().product();
        let strides = compute_strides(&dims);
        Self {
            data: vec![0u32; total],
            dims,
            strides,
        }
    }

    /// フラットインデックス計算（row-major: strides[0]=1, strides[i]=∏dims[0..i]）
    #[inline]
    pub fn flat_idx(&self, coords: &[usize]) -> usize {
        debug_assert_eq!(coords.len(), self.dims.len());
        coords
            .iter()
            .zip(self.strides.iter())
            .map(|(c, s)| c * s)
            .sum()
    }

    #[inline]
    pub fn get(&self, coords: &[usize]) -> u32 {
        self.data[self.flat_idx(coords)]
    }

    #[inline]
    pub fn add(&mut self, coords: &[usize], v: u32) {
        let i = self.flat_idx(coords);
        self.data[i] += v;
    }

    /// 全セルの座標をイテレートする
    pub fn iter_coords(&self) -> impl Iterator<Item = Vec<usize>> + '_ {
        iter_coords_impl(&self.dims)
    }
}

/// strides 計算: strides[0]=1, strides[i]=strides[i-1]*dims[i-1]
fn compute_strides(dims: &[usize]) -> Vec<usize> {
    let d = dims.len();
    let mut strides = vec![1usize; d];
    for i in 1..d {
        strides[i] = strides[i - 1] * dims[i - 1];
    }
    strides
}

/// 全座標をイテレートするジェネレータ（row-major 順）
fn iter_coords_impl(dims: &[usize]) -> impl Iterator<Item = Vec<usize>> + '_ {
    let total: usize = dims.iter().product();
    let strides = compute_strides(dims);
    (0..total).map(move |flat| {
        let mut coords = vec![0usize; dims.len()];
        let mut rem = flat;
        // strides は昇順なので逆順にデコード
        for i in (0..dims.len()).rev() {
            coords[i] = rem / strides[i];
            rem %= strides[i];
        }
        coords
    })
}

// ---------------------------------------------------------------------------
// PrefixSumND
// ---------------------------------------------------------------------------

/// d 次元接頭辞和（各次元 +1 パディング）
#[derive(Debug, Clone)]
pub struct PrefixSumND {
    pub data: Vec<u64>,
    pub dims: Vec<usize>, // dims[i] = grid.dims[i] + 1
    strides: Vec<usize>,
}

impl PrefixSumND {
    #[inline]
    pub fn flat_idx(&self, coords: &[usize]) -> usize {
        coords
            .iter()
            .zip(self.strides.iter())
            .map(|(c, s)| c * s)
            .sum()
    }

    #[inline]
    pub fn get(&self, coords: &[usize]) -> u64 {
        self.data[self.flat_idx(coords)]
    }
}

/// d 次元接頭辞和構築 O(∏dims_i)
///
/// 構築手順:
/// 1. ps[coords[i]+1 for all i] = grid[coords] を全セルにセット
/// 2. 各次元 d について: d 方向に累積和をとる
pub fn build_prefix_sum_nd(grid: &GridND) -> PrefixSumND {
    let d = grid.dims.len();
    let ps_dims: Vec<usize> = grid.dims.iter().map(|&s| s + 1).collect();
    let ps_strides = compute_strides(&ps_dims);
    let total: usize = ps_dims.iter().product();
    let mut data = vec![0u64; total];

    // Step 1: グリッド値をシフトして配置
    for coords in grid.iter_coords() {
        let v = grid.get(&coords) as u64;
        if v == 0 {
            continue;
        }
        let ps_coords: Vec<usize> = coords.iter().map(|&c| c + 1).collect();
        let idx: usize = ps_coords
            .iter()
            .zip(ps_strides.iter())
            .map(|(c, s)| c * s)
            .sum();
        data[idx] = v;
    }

    // Step 2: 各次元について累積和
    for dim in 0..d {
        // dim 次元以外は全座標をイテレート、dim 方向に 1..ps_dims[dim] を累積
        // 補助関数: dim_stride = ps_strides[dim]
        let dim_stride = ps_strides[dim];
        let dim_size = ps_dims[dim];

        // dim 次元を除いた全座標をイテレート
        let other_dims: Vec<usize> = ps_dims
            .iter()
            .enumerate()
            .filter(|&(i, _)| i != dim)
            .map(|(_, &s)| s)
            .collect();
        let other_strides: Vec<usize> = ps_strides
            .iter()
            .enumerate()
            .filter(|&(i, _)| i != dim)
            .map(|(_, &s)| s)
            .collect();

        let other_total: usize = other_dims.iter().product();
        let other_strides_local = compute_strides(&other_dims);

        for flat_other in 0..other_total {
            // flat_other → 他次元の座標
            let mut base_idx = 0usize;
            let mut rem = flat_other;
            for i in (0..other_dims.len()).rev() {
                let c = rem / other_strides_local[i];
                rem %= other_strides_local[i];
                base_idx += c * other_strides[i];
            }

            // dim 方向に累積
            for d_pos in 1..dim_size {
                let cur = base_idx + d_pos * dim_stride;
                let prev = base_idx + (d_pos - 1) * dim_stride;
                data[cur] += data[prev];
            }
        }
    }

    PrefixSumND {
        data,
        dims: ps_dims,
        strides: ps_strides,
    }
}

/// 範囲 [starts[i], starts[i]+windows[i]) の合計 O(2^d)
///
/// 包除原理: mask ∈ 0..2^d を列挙
/// bit i が立っていれば upper[i] = starts[i]+windows[i]、なければ lower[i] = starts[i]
/// 符号 = (-1)^(d - popcount(mask)) = (-1)^(ゼロビット数)
pub fn query_range_nd(ps: &PrefixSumND, starts: &[usize], windows: &[usize]) -> u32 {
    let d = ps.dims.len();
    debug_assert_eq!(starts.len(), d);
    debug_assert_eq!(windows.len(), d);

    // 境界クランプ
    let lowers: Vec<usize> = starts.to_vec();
    let uppers: Vec<usize> = starts
        .iter()
        .zip(windows.iter())
        .zip(ps.dims.iter())
        .map(|((s, w), &pd)| (s + w).min(pd - 1))
        .collect();

    // 有効性チェック
    for i in 0..d {
        if lowers[i] >= uppers[i] {
            return 0;
        }
    }

    let n_masks = 1usize << d;
    let mut sum: i64 = 0;

    for mask in 0..n_masks {
        let mut coords = vec![0usize; d];
        let mut zero_bits = 0u32;
        for i in 0..d {
            if (mask >> i) & 1 == 1 {
                coords[i] = uppers[i];
            } else {
                coords[i] = lowers[i];
                zero_bits += 1;
            }
        }
        let val = ps.get(&coords) as i64;
        if zero_bits % 2 == 0 {
            sum += val;
        } else {
            sum -= val;
        }
    }

    sum.max(0) as u32
}

/// サポートサーフェス計算（全グリッド点）O(∏dims_i)
pub fn compute_support_surface_nd(ps: &PrefixSumND, windows: &[usize]) -> GridND {
    let grid_dims: Vec<usize> = ps.dims.iter().map(|&s| s - 1).collect();
    let mut surface = GridND::new(grid_dims.clone());

    for coords in surface.iter_coords().collect::<Vec<_>>() {
        // starts = coords（グリッド座標）
        let starts: Vec<usize> = coords.clone();
        let v = query_range_nd(ps, &starts, windows);
        let idx = surface.flat_idx(&coords);
        surface.data[idx] = v;
    }
    surface
}

// ---------------------------------------------------------------------------
// バイナリサーチ版サポート計算
// ---------------------------------------------------------------------------

/// 空間セル（次元 1..d）→ ソート済み時刻ビンリスト のマップを走査する内部ヘルパー
fn iter_spatial_cells(ranges: &[std::ops::Range<usize>], f: &mut impl FnMut(&[usize])) {
    if ranges.iter().any(|r| r.is_empty()) {
        return;
    }
    if ranges.is_empty() {
        f(&[]);
        return;
    }
    let mut coords: Vec<usize> = ranges.iter().map(|r| r.start).collect();
    loop {
        f(&coords);
        let mut carry = true;
        for i in (0..ranges.len()).rev() {
            if carry {
                coords[i] += 1;
                if coords[i] < ranges[i].end {
                    carry = false;
                } else {
                    coords[i] = ranges[i].start;
                }
            }
        }
        if carry {
            break;
        }
    }
}

/// ウィンドウ開始点 `s` に対するバイナリサーチ版サポート計算
///
/// - `cell_time_map`: 空間座標（次元 1..d、長さ d-1）→ ソート済み時刻ビン
/// - 計算量: O(∏_{k≥1} W_k × log N)
pub fn query_binsearch_nd(
    cell_time_map: &HashMap<Vec<usize>, Vec<usize>>,
    s: &[usize],
    windows: &[usize],
    dims: &[usize],
) -> u32 {
    let d = s.len();
    let t_start = s[0];
    let t_end = t_start + windows[0];

    let mut count = 0u32;

    if d == 1 {
        // 空間次元なし：キーは空ベクタ
        if let Some(times) = cell_time_map.get(&vec![]) {
            let lo = times.partition_point(|&t| t < t_start);
            let hi = times.partition_point(|&t| t < t_end);
            count += (hi - lo) as u32;
        }
    } else {
        let spatial_ranges: Vec<std::ops::Range<usize>> = (1..d)
            .map(|k| s[k]..((s[k] + windows[k]).min(dims[k])))
            .collect();
        iter_spatial_cells(&spatial_ranges, &mut |spatial_coords: &[usize]| {
            if let Some(times) = cell_time_map.get(spatial_coords) {
                let lo = times.partition_point(|&t| t < t_start);
                let hi = times.partition_point(|&t| t < t_end);
                count += (hi - lo) as u32;
            }
        });
    }

    count
}

/// バイナリサーチ版サポートサーフェス計算（全グリッド点）O(G × ∏_{k≥1} W_k × log N)
pub fn compute_support_surface_binsearch_nd(
    cell_time_map: &HashMap<Vec<usize>, Vec<usize>>,
    dims: &[usize],
    windows: &[usize],
) -> GridND {
    let mut surface = GridND::new(dims.to_vec());
    for s in surface.iter_coords().collect::<Vec<_>>() {
        let v = query_binsearch_nd(cell_time_map, &s, windows, dims);
        let idx = surface.flat_idx(&s);
        surface.data[idx] = v;
    }
    surface
}

/// 密集セル抽出（support >= theta）
pub fn find_dense_cells_nd(surface: &GridND, theta: u32) -> Vec<Vec<usize>> {
    surface
        .iter_coords()
        .filter(|coords| surface.get(coords) >= theta)
        .collect()
}

// ---------------------------------------------------------------------------
// 2d-近傍 Union-Find 連結成分
// ---------------------------------------------------------------------------

fn uf_find(parent: &mut Vec<usize>, x: usize) -> usize {
    if parent[x] != x {
        parent[x] = uf_find(parent, parent[x]);
    }
    parent[x]
}

fn uf_union(parent: &mut Vec<usize>, rank: &mut Vec<u8>, a: usize, b: usize) {
    let ra = uf_find(parent, a);
    let rb = uf_find(parent, b);
    if ra == rb {
        return;
    }
    if rank[ra] < rank[rb] {
        parent[ra] = rb;
    } else if rank[ra] > rank[rb] {
        parent[rb] = ra;
    } else {
        parent[rb] = ra;
        rank[ra] += 1;
    }
}

/// 2d-近傍（各次元 ±1）Union-Find 連結成分
pub fn connected_components_nd(dense_cells: &[Vec<usize>], dims: &[usize]) -> Vec<Vec<Vec<usize>>> {
    if dense_cells.is_empty() {
        return Vec::new();
    }

    let d = dims.len();

    // セル座標 → インデックスの逆引きマップ（フラットキー使用）
    let strides = compute_strides(dims);
    let cell_to_flat = |coords: &Vec<usize>| -> usize {
        coords.iter().zip(strides.iter()).map(|(c, s)| c * s).sum()
    };

    let cell_idx: HashMap<usize, usize> = dense_cells
        .iter()
        .enumerate()
        .map(|(i, c)| (cell_to_flat(c), i))
        .collect();

    let n = dense_cells.len();
    let mut parent: Vec<usize> = (0..n).collect();
    let mut rank = vec![0u8; n];

    for (i, cell) in dense_cells.iter().enumerate() {
        // 各次元について ±1 の近傍をチェック
        for dim in 0..d {
            for delta in [-1i64, 1i64] {
                let new_pos = cell[dim] as i64 + delta;
                if new_pos < 0 || new_pos as usize >= dims[dim] {
                    continue;
                }
                let mut neighbor = cell.clone();
                neighbor[dim] = new_pos as usize;
                let nflat = cell_to_flat(&neighbor);
                if let Some(&j) = cell_idx.get(&nflat) {
                    uf_union(&mut parent, &mut rank, i, j);
                }
            }
        }
    }

    // グループ化
    let mut groups: HashMap<usize, Vec<Vec<usize>>> = HashMap::new();
    for (i, cell) in dense_cells.iter().enumerate() {
        let root = uf_find(&mut parent, i);
        groups.entry(root).or_default().push(cell.clone());
    }

    groups.into_values().collect()
}

// ---------------------------------------------------------------------------
// テスト
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ----- GridND 基本テスト -----

    #[test]
    fn test_grid_nd_flat_idx_2d() {
        // 2×3 グリッド: strides = [1, 2]
        let g = GridND::new(vec![2, 3]);
        assert_eq!(g.flat_idx(&[0, 0]), 0);
        assert_eq!(g.flat_idx(&[1, 0]), 1);
        assert_eq!(g.flat_idx(&[0, 1]), 2);
        assert_eq!(g.flat_idx(&[1, 2]), 5);
    }

    #[test]
    fn test_grid_nd_add_get() {
        let mut g = GridND::new(vec![3, 3, 3]);
        g.add(&[1, 2, 0], 7);
        assert_eq!(g.get(&[1, 2, 0]), 7);
        assert_eq!(g.get(&[0, 0, 0]), 0);
    }

    // ----- 接頭辞和 2×2 正確性 -----

    #[test]
    fn test_prefix_sum_nd_2x2() {
        let mut g = GridND::new(vec![2, 2]);
        for x in 0..2 {
            for y in 0..2 {
                g.add(&[x, y], 1);
            }
        }
        let ps = build_prefix_sum_nd(&g);
        // 全セル = 4
        assert_eq!(query_range_nd(&ps, &[0, 0], &[2, 2]), 4);
        // 左上 1セル
        assert_eq!(query_range_nd(&ps, &[0, 0], &[1, 1]), 1);
        // 右下 1セル
        assert_eq!(query_range_nd(&ps, &[1, 1], &[1, 1]), 1);
    }

    // ----- d=2（1D タイムライン）ブルートフォース比較 -----

    #[test]
    fn test_prefix_sum_nd_1d_brute_force() {
        // 次元 d=1 として扱う（dims=[N]）
        let n = 10usize;
        let values: Vec<u32> = (0..n).map(|i| (i % 3) as u32 + 1).collect();
        let mut g = GridND::new(vec![n]);
        for i in 0..n {
            g.add(&[i], values[i]);
        }
        let ps = build_prefix_sum_nd(&g);

        // 全 [s, s+w) 区間についてブルートフォースと比較
        for s in 0..n {
            for w in 1..=(n - s) {
                let expected: u32 = values[s..s + w].iter().sum();
                let got = query_range_nd(&ps, &[s], &[w]);
                assert_eq!(
                    got, expected,
                    "1D: s={} w={}: got={} expected={}",
                    s, w, got, expected
                );
            }
        }
    }

    // ----- d=3 で grid3d との等価性 -----

    #[test]
    fn test_prefix_sum_nd_3d_vs_grid3d() {
        use crate::grid3d::{build_prefix_sum, query_range, Grid3D};

        let t = 4usize;
        let x = 3usize;
        let y = 3usize;

        // 同じデータで両方を構築
        let mut g3 = Grid3D::new(t, x, y);
        let mut gn = GridND::new(vec![t, x, y]);

        // 疎なデータを注入
        let points = [(0, 0, 0, 5u32), (1, 2, 1, 3), (3, 0, 2, 7), (2, 1, 0, 1)];
        for (ti, xi, yi, v) in points {
            g3.add(ti, xi, yi, v);
            gn.add(&[ti, xi, yi], v);
        }

        let ps3 = build_prefix_sum(&g3);
        let psn = build_prefix_sum_nd(&gn);

        // 全ウィンドウで比較
        let wt_list = [1, 2, 3];
        let wx_list = [1, 2];
        let wy_list = [1, 2];
        for &wt in &wt_list {
            for &wx in &wx_list {
                for &wy in &wy_list {
                    for ti in 0..t {
                        for xi in 0..x {
                            for yi in 0..y {
                                let v3 = query_range(&ps3, ti, xi, yi, wt, wx, wy);
                                let vn = query_range_nd(&psn, &[ti, xi, yi], &[wt, wx, wy]);
                                assert_eq!(
                                    v3, vn,
                                    "3D vs ND mismatch at ({},{},{}) w=({},{},{}): {} vs {}",
                                    ti, xi, yi, wt, wx, wy, v3, vn
                                );
                            }
                        }
                    }
                }
            }
        }
    }

    // ----- connected_components_nd テスト -----

    #[test]
    fn test_connected_components_nd_single() {
        let cells = vec![vec![0usize, 0usize]];
        let comps = connected_components_nd(&cells, &[3, 3]);
        assert_eq!(comps.len(), 1);
        assert_eq!(comps[0].len(), 1);
    }

    #[test]
    fn test_connected_components_nd_two_separate() {
        // (0,0) と (2,2) は隣接しない → 2 成分
        let cells = vec![vec![0usize, 0], vec![2, 2]];
        let comps = connected_components_nd(&cells, &[3, 3]);
        assert_eq!(comps.len(), 2);
    }

    #[test]
    fn test_connected_components_nd_chain() {
        // (0,0)-(1,0)-(2,0) は連鎖 → 1 成分
        let cells = vec![vec![0usize, 0], vec![1, 0], vec![2, 0]];
        let comps = connected_components_nd(&cells, &[3, 3]);
        assert_eq!(comps.len(), 1);
        assert_eq!(comps[0].len(), 3);
    }

    #[test]
    fn test_connected_components_nd_two_components() {
        // 2 クラスタ: [(0,0),(1,0)] と [(3,3),(3,4)]
        let cells = vec![vec![0usize, 0], vec![1, 0], vec![3, 3], vec![3, 4]];
        let comps = connected_components_nd(&cells, &[5, 5]);
        assert_eq!(comps.len(), 2);
        let sizes: Vec<usize> = {
            let mut s: Vec<usize> = comps.iter().map(|c| c.len()).collect();
            s.sort_unstable();
            s
        };
        assert_eq!(sizes, vec![2, 2]);
    }

    #[test]
    fn test_connected_components_nd_3d() {
        // 3D 空間で連結確認: (0,0,0)-(1,0,0)-(1,1,0) → 1成分
        let cells = vec![vec![0, 0, 0usize], vec![1, 0, 0], vec![1, 1, 0]];
        let comps = connected_components_nd(&cells, &[3, 3, 3]);
        assert_eq!(comps.len(), 1);
        assert_eq!(comps[0].len(), 3);
    }

    #[test]
    fn test_connected_components_nd_empty() {
        let cells: Vec<Vec<usize>> = Vec::new();
        let comps = connected_components_nd(&cells, &[3, 3]);
        assert!(comps.is_empty());
    }

    // ----- find_dense_cells_nd テスト -----

    #[test]
    fn test_find_dense_cells_nd() {
        let mut surface = GridND::new(vec![2, 2]);
        surface.add(&[0, 0], 5);
        surface.add(&[1, 1], 2);
        let cells = find_dense_cells_nd(&surface, 3);
        assert_eq!(cells.len(), 1);
        assert_eq!(cells[0], vec![0, 0]);
    }
}
