//! 3D グリッド・プレフィックスサム・連結成分
//!
//! # 設計
//! - `Grid3D`: フラット配列で T×X×Y グリッドを保持
//! - `PrefixSum3D`: 8コーナー包除原理による O(1) 範囲クエリ
//! - `connected_components_6`: 6近傍 Union-Find

// ---------------------------------------------------------------------------
// Grid3D
// ---------------------------------------------------------------------------

/// T×X×Y の3次元グリッド（フラット配列）
#[derive(Debug, Clone)]
pub struct Grid3D {
    pub data: Vec<u32>,
    pub dims: (usize, usize, usize), // (T, X, Y)
}

impl Grid3D {
    pub fn new(t: usize, x: usize, y: usize) -> Self {
        Self {
            data: vec![0u32; t * x * y],
            dims: (t, x, y),
        }
    }

    #[inline]
    pub fn idx(&self, ti: usize, xi: usize, yi: usize) -> usize {
        let (_, x, y) = self.dims;
        ti * x * y + xi * y + yi
    }

    #[inline]
    pub fn get(&self, ti: usize, xi: usize, yi: usize) -> u32 {
        self.data[self.idx(ti, xi, yi)]
    }

    #[inline]
    pub fn add(&mut self, ti: usize, xi: usize, yi: usize, v: u32) {
        let i = self.idx(ti, xi, yi);
        self.data[i] += v;
    }
}

// ---------------------------------------------------------------------------
// PrefixSum3D
// ---------------------------------------------------------------------------

/// 3D プレフィックスサム（サイズは (T+1)×(X+1)×(Y+1)）
#[derive(Debug, Clone)]
pub struct PrefixSum3D {
    pub data: Vec<u64>,
    pub dims: (usize, usize, usize), // (T+1, X+1, Y+1)
}

impl PrefixSum3D {
    #[inline]
    fn idx(&self, ti: usize, xi: usize, yi: usize) -> usize {
        let (_, x1, y1) = self.dims;
        ti * x1 * y1 + xi * y1 + yi
    }

    #[inline]
    fn get(&self, ti: usize, xi: usize, yi: usize) -> u64 {
        self.data[self.idx(ti, xi, yi)]
    }
}

/// 3D プレフィックスサム構築 O(T·X·Y)
pub fn build_prefix_sum(grid: &Grid3D) -> PrefixSum3D {
    let (t, x, y) = grid.dims;
    let t1 = t + 1;
    let x1 = x + 1;
    let y1 = y + 1;
    let mut ps = PrefixSum3D {
        data: vec![0u64; t1 * x1 * y1],
        dims: (t1, x1, y1),
    };

    // ps[ti+1][xi+1][yi+1] = grid[ti][xi][yi] + ... (包除で構築)
    for ti in 0..t {
        for xi in 0..x {
            for yi in 0..y {
                let v = grid.get(ti, xi, yi) as u64;
                let i = ps.idx(ti + 1, xi + 1, yi + 1);
                ps.data[i] = v
                    + ps.get(ti, xi + 1, yi + 1)
                    + ps.get(ti + 1, xi, yi + 1)
                    + ps.get(ti + 1, xi + 1, yi)
                    - ps.get(ti, xi, yi + 1)
                    - ps.get(ti, xi + 1, yi)
                    - ps.get(ti + 1, xi, yi)
                    + ps.get(ti, xi, yi);
            }
        }
    }
    ps
}

/// 範囲 [t0, t0+wt) × [x0, x0+wx) × [y0, y0+wy) の合計 O(1)
pub fn query_range(
    ps: &PrefixSum3D,
    t0: usize,
    x0: usize,
    y0: usize,
    wt: usize,
    wx: usize,
    wy: usize,
) -> u32 {
    let (t1, x1, y1) = ps.dims;
    let t_end = (t0 + wt).min(t1 - 1);
    let x_end = (x0 + wx).min(x1 - 1);
    let y_end = (y0 + wy).min(y1 - 1);

    if t0 >= t_end || x0 >= x_end || y0 >= y_end {
        return 0;
    }

    // i64 にキャストしてから包除演算（中間値が負になる可能性があるため）
    let v = ps.get(t_end, x_end, y_end) as i64
        - ps.get(t0, x_end, y_end) as i64
        - ps.get(t_end, x0, y_end) as i64
        - ps.get(t_end, x_end, y0) as i64
        + ps.get(t0, x0, y_end) as i64
        + ps.get(t0, x_end, y0) as i64
        + ps.get(t_end, x0, y0) as i64
        - ps.get(t0, x0, y0) as i64;

    v.max(0) as u32
}

/// 全グリッド点のサポートサーフェス計算 O(T·X·Y)
pub fn compute_support_surface(ps: &PrefixSum3D, wt: usize, wx: usize, wy: usize) -> Grid3D {
    let (t1, x1, y1) = ps.dims;
    let t = t1 - 1;
    let x = x1 - 1;
    let y = y1 - 1;
    let mut surface = Grid3D::new(t, x, y);
    for ti in 0..t {
        for xi in 0..x {
            for yi in 0..y {
                let v = query_range(ps, ti, xi, yi, wt, wx, wy);
                let i = surface.idx(ti, xi, yi);
                surface.data[i] = v;
            }
        }
    }
    surface
}

/// 密集セル抽出（support >= theta）
pub fn find_dense_cells(surface: &Grid3D, theta: u32) -> Vec<(usize, usize, usize)> {
    let (t, x, y) = surface.dims;
    let mut cells = Vec::new();
    for ti in 0..t {
        for xi in 0..x {
            for yi in 0..y {
                if surface.get(ti, xi, yi) >= theta {
                    cells.push((ti, xi, yi));
                }
            }
        }
    }
    cells
}

// ---------------------------------------------------------------------------
// 6近傍 Union-Find 連結成分
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

/// 6近傍（±t, ±x, ±y）連結成分を Union-Find で計算
pub fn connected_components_6(
    dense_cells: &[(usize, usize, usize)],
    dims: (usize, usize, usize),
) -> Vec<Vec<(usize, usize, usize)>> {
    if dense_cells.is_empty() {
        return Vec::new();
    }

    let (_, x, y) = dims;

    // セル座標 → インデックスの逆引きマップ
    use std::collections::HashMap;
    let cell_idx: HashMap<(usize, usize, usize), usize> = dense_cells
        .iter()
        .enumerate()
        .map(|(i, &c)| (c, i))
        .collect();

    let n = dense_cells.len();
    let mut parent: Vec<usize> = (0..n).collect();
    let mut rank = vec![0u8; n];

    for (i, &(ti, xi, yi)) in dense_cells.iter().enumerate() {
        // 6近傍（前方向のみチェック、後は対称なのでスキップ）
        let neighbors: &[(i64, i64, i64)] = &[
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (-1, 0, 0),
            (0, -1, 0),
            (0, 0, -1),
        ];
        for &(dt, dx, dy) in neighbors {
            let nt = ti as i64 + dt;
            let nx = xi as i64 + dx;
            let ny = yi as i64 + dy;
            if nt < 0 || nx < 0 || ny < 0 {
                continue;
            }
            let (nt, nx, ny) = (nt as usize, nx as usize, ny as usize);
            if nt >= dims.0 || nx >= x || ny >= y {
                continue;
            }
            if let Some(&j) = cell_idx.get(&(nt, nx, ny)) {
                uf_union(&mut parent, &mut rank, i, j);
            }
        }
    }

    // グループ化
    let mut groups: HashMap<usize, Vec<(usize, usize, usize)>> = HashMap::new();
    for (i, &cell) in dense_cells.iter().enumerate() {
        let root = uf_find(&mut parent, i);
        groups.entry(root).or_default().push(cell);
    }

    groups.into_values().collect()
}

// ---------------------------------------------------------------------------
// テスト
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prefix_sum_2x2x2() {
        let mut g = Grid3D::new(2, 2, 2);
        // 全セルに 1 を設定
        for ti in 0..2 {
            for xi in 0..2 {
                for yi in 0..2 {
                    g.add(ti, xi, yi, 1);
                }
            }
        }
        let ps = build_prefix_sum(&g);
        // ウィンドウ [0,2)×[0,2)×[0,2) = 全セル = 8
        assert_eq!(query_range(&ps, 0, 0, 0, 2, 2, 2), 8);
        // ウィンドウ [0,1)×[0,1)×[0,1) = 1セル = 1
        assert_eq!(query_range(&ps, 0, 0, 0, 1, 1, 1), 1);
        // ウィンドウ [1,2)×[1,2)×[1,2) = 1セル = 1
        assert_eq!(query_range(&ps, 1, 1, 1, 1, 1, 1), 1);
    }

    #[test]
    fn test_prefix_sum_sparse() {
        let mut g = Grid3D::new(4, 4, 4);
        g.add(0, 0, 0, 5);
        g.add(3, 3, 3, 3);
        let ps = build_prefix_sum(&g);
        assert_eq!(query_range(&ps, 0, 0, 0, 1, 1, 1), 5);
        assert_eq!(query_range(&ps, 3, 3, 3, 1, 1, 1), 3);
        assert_eq!(query_range(&ps, 0, 0, 0, 4, 4, 4), 8);
        assert_eq!(query_range(&ps, 1, 1, 1, 2, 2, 2), 0);
    }

    #[test]
    fn test_prefix_sum_window_clamp() {
        // ウィンドウがグリッド端を超えても正しく動作する
        let mut g = Grid3D::new(3, 3, 3);
        g.add(2, 2, 2, 10);
        let ps = build_prefix_sum(&g);
        // ウィンドウ [2,5) → クランプされて [2,3)
        assert_eq!(query_range(&ps, 2, 2, 2, 3, 3, 3), 10);
    }

    #[test]
    fn test_connected_components_single() {
        let cells = vec![(0usize, 0usize, 0usize)];
        let comps = connected_components_6(&cells, (3, 3, 3));
        assert_eq!(comps.len(), 1);
        assert_eq!(comps[0].len(), 1);
    }

    #[test]
    fn test_connected_components_two_separate() {
        // (0,0,0) と (2,2,2) は隣接しない → 2成分
        let cells = vec![(0, 0, 0), (2, 2, 2)];
        let comps = connected_components_6(&cells, (3, 3, 3));
        assert_eq!(comps.len(), 2);
    }

    #[test]
    fn test_connected_components_chain() {
        // (0,0,0)-(1,0,0)-(2,0,0) は全部つながる → 1成分
        let cells = vec![(0, 0, 0), (1, 0, 0), (2, 0, 0)];
        let comps = connected_components_6(&cells, (3, 3, 3));
        assert_eq!(comps.len(), 1);
        assert_eq!(comps[0].len(), 3);
    }

    #[test]
    fn test_find_dense_cells() {
        let mut surface = Grid3D::new(2, 2, 2);
        surface.add(0, 0, 0, 5);
        surface.add(1, 1, 1, 2);
        let cells = find_dense_cells(&surface, 3);
        assert_eq!(cells.len(), 1);
        assert_eq!(cells[0], (0, 0, 0));
    }
}
