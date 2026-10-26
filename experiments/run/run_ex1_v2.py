"""
EX-1 v2: 比較実験（全4データセット）

EX-1-1: 密集パターン検出精度（F1）
  Chicago Crime / NYPD Crime / NYC 311 / USGS EQ (4D)
  比較手法: Colocation, STCP-Miner, M-Zoom, M-Biz, D-Cube, CatchCore

EX-1-2: 密集領域復元精度（mean Jaccard）
  全4データセット
  比較手法: M-Zoom, M-Biz, D-Cube, CatchCore

変更点 (vs run_ex1_comparison_3d.py):
  - BINパスを apriori_window_md に修正
  - NYC 311 / USGS EQ を追加（全4データセット）
  - dense-block 系 baseline を公式実装 wrapper に切替
    (M-Zoom / M-Biz / D-Cube / CatchCore)
  - USGS は 4次元対応 (load_tsv_nd)
  - EX-1-2 も全4データセットに拡張
  - md_pipeline の interval summary 出力
    (n_slices, total_intervals, total_span) に追従
  - EX-1-2 は全 GT パターンの exact dense-start 集合で評価
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

try:
    from denseblock_wrappers import (
        collect_catchcore_blocks_official,
        collect_dcube_blocks_official,
        collect_mbiz_blocks_official,
        collect_mzoom_blocks_official,
    )
except ModuleNotFoundError:
    from experiments.denseblock_wrappers import (
        collect_catchcore_blocks_official,
        collect_dcube_blocks_official,
        collect_mbiz_blocks_official,
        collect_mzoom_blocks_official,
    )

# ---------------------------------------------------------------------------
# パス設定
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "apriori_window_md" / "target" / "release" / "md_pipeline"
DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR = Path(__file__).resolve().parent / "results" / "ex1_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not BIN.exists():
    sys.exit(f"Error: binary not found: {BIN}\nRun: cd apriori_window_md && cargo build --release")

# ---------------------------------------------------------------------------
# データセット設定
# ---------------------------------------------------------------------------

DATASETS = {
    "chicago": {
        "tsv": DATA_DIR / "chicago_crime_3d_bs0p020.tsv",
        "meta": DATA_DIR / "chicago_crime_3d_bs0p020_meta.json",
        "window": "54,5,5",
        "threshold": 1000,
        "n_dims": 3,
    },
    "nypd": {
        "tsv": DATA_DIR / "nyc_crime_3d_bs0p010.tsv",
        "meta": DATA_DIR / "nyc_crime_3d_bs0p010_meta.json",
        "window": "54,5,5",
        "threshold": 1000,
        "n_dims": 3,
    },
    "nyc_311": {
        "tsv": DATA_DIR / "nyc_311_3d_bs0p010.tsv",
        "meta": DATA_DIR / "nyc_311_3d_bs0p010_meta.json",
        "window": "54,5,5",
        "threshold": 1200,
        "n_dims": 3,
    },
    "usgs_eq": {
        "tsv": DATA_DIR / "usgs_eq_4d_california_blat0.5_blon0.5_bdep35.tsv",
        "meta": DATA_DIR / "usgs_eq_4d_california_blat0.5_blon0.5_bdep35_meta.json",
        "window": "54,5,5,5",
        "threshold": 3,
        "n_dims": 4,
    },
}

# EX-1-1 グリッドサーチパラメータ
COLOC_TAU_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
STCP_TAU_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
STCP_WINDOW_GRID = [4, 8, 13, 26, 54]
MZOOM_TOP_K = 100
MZOOM_MAX_ENTRIES = 2_000_000
MZOOM_DENSITY_MEASURES = ["geo", "ari", "susp"]
DCUBE_POLICY_GRID = ["density"]
DCUBE_MASS_THRESHOLD_GRID = [1.0]
CATCHCORE_HS_GRID = [3]
CATCHCORE_P_GRID = [1e-3]
CATCHCORE_CONS_GRID = [20.0]
CATCHCORE_ETAS_GRID = [10.0]

# EX-1-2 グリッドサーチパラメータ
ST_EPS1_GRID = [1, 2, 3]
ST_EPS2_GRID = [1, 2, 4, 8]
ST_MINPTS_GRID = [2, 3, 5]
LISA_WEIGHT_TYPES = ["queen", "rook", "knn3", "knn5"]

# EX-1-1 ST-DBSCAN/LISA ベストパラメータ（Chicago EX-1-2 結果から固定）
STDBSCAN_FIXED_EPS1 = 3
STDBSCAN_FIXED_EPS2 = 8
STDBSCAN_FIXED_MIN_PTS = 2
LISA_FIXED_WEIGHT = "knn5"

# EX-1-1 代表パターン数上限（ST-DBSCAN/LISA は時間がかかるため）
MAX_PATTERNS_STDBSCAN_LISA = 50

TIMEOUT_S = 30 * 60  # 各データセット最大 30 分（警告用）
EX1_MAX_PATTERN_SIZE = 3


# ===========================================================================
# データ読み込みユーティリティ
# ===========================================================================

def load_tsv(tsv_path: Path) -> tuple[dict[tuple, frozenset], int, int, int, int]:
    """3D TSV を読み込んで cell_items と グリッドサイズを返す。"""
    cell_items: dict[tuple, set] = defaultdict(set)
    with open(tsv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            t, x, y = int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
            for v in parts[3].split(","):
                v = v.strip()
                if v:
                    cell_items[(t, x, y)].add(int(v))
    result = {k: frozenset(v) for k, v in cell_items.items()}
    if not result:
        return result, 0, 0, 0, 0
    ts = [k[0] for k in result]
    xs = [k[1] for k in result]
    ys = [k[2] for k in result]
    return result, max(ts)+1, max(xs)+1, max(ys)+1, len(result)


def load_tsv_nd(tsv_path: Path, n_dims: int) -> tuple[dict[tuple, frozenset], list[int], int]:
    """
    d次元TSVを読み込む。
    Returns: (cell_items, dim_sizes, n_cells)
      cell_items: (d0, d1, ..., d_{n_dims-1}) -> frozenset of items
      dim_sizes: [max+1 for each dim]
    """
    cell_items: dict[tuple, set] = defaultdict(set)
    with open(tsv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < n_dims + 1:
                continue
            coords = tuple(int(float(parts[d])) for d in range(n_dims))
            items_str = parts[n_dims]
            for v in items_str.split(","):
                v = v.strip()
                if v:
                    cell_items[coords].add(int(v))
    result = {k: frozenset(v) for k, v in cell_items.items()}
    if not result:
        return result, [0] * n_dims, 0
    dim_sizes = [max(k[d] for k in result) + 1 for d in range(n_dims)]
    return result, dim_sizes, len(result)


def load_meta(meta_path: Path) -> dict:
    with open(meta_path) as f:
        return json.load(f)


# ===========================================================================
# md_pipeline 実行 + GT 構築
# ===========================================================================

def run_md_pipeline(
    tsv_path: Path,
    window: str,
    threshold: int,
    n_dims: int = 3,
    max_length: int | None = None,
) -> tuple[dict[tuple, dict], float]:
    """md_pipeline を実行して interval summary 付きパターン辞書を返す。"""
    cmd = [
        str(BIN), "run",
        "--input", str(tsv_path),
        "--n-dims", str(n_dims),
        "--window", window,
        "--threshold", str(threshold),
    ]
    if max_length is not None:
        cmd.extend(["--max-length", str(max_length)])
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"md_pipeline failed for {tsv_path.name}:\n{proc.stderr}")

    patterns = {}
    for line in proc.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            items = tuple(sorted(int(x) for x in parts[0].split(",")))
            if max_length is not None and len(items) > max_length:
                continue
            patterns[items] = {
                "n_slices": int(parts[1]),
                "total_intervals": int(parts[2]),
                "total_span": int(parts[3]),
            }
    return patterns, elapsed


def build_item_cells_map(cell_items: dict[tuple, frozenset]) -> dict[int, set[tuple]]:
    item_cells_map: dict[int, set[tuple]] = defaultdict(set)
    for cell, items in cell_items.items():
        cell_t = tuple(cell)
        for item in items:
            item_cells_map[item].add(cell_t)
    return item_cells_map


def intersect_item_cells(
    pattern: tuple[int, ...],
    item_cells_map: dict[int, set[tuple]],
    cache: dict[tuple[int, ...], set[tuple]] | None = None,
) -> set[tuple]:
    if cache is not None and pattern in cache:
        return cache[pattern]

    singleton_sets = [item_cells_map.get(item, set()) for item in pattern]
    if not singleton_sets or any(not cells for cells in singleton_sets):
        result: set[tuple] = set()
    else:
        ordered = sorted(singleton_sets, key=len)
        result = set(ordered[0])
        for cells in ordered[1:]:
            result.intersection_update(cells)
            if not result:
                break

    if cache is not None:
        cache[pattern] = result
    return result


def generate_apriori_candidates(prev_level: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    if not prev_level:
        return []

    k = len(prev_level[0]) + 1
    prev_sorted = sorted(prev_level)
    prev_set = set(prev_sorted)
    candidates = set()

    for i in range(len(prev_sorted)):
        for j in range(i + 1, len(prev_sorted)):
            if k > 2 and prev_sorted[i][: k - 2] != prev_sorted[j][: k - 2]:
                break
            cand = tuple(sorted(set(prev_sorted[i]) | set(prev_sorted[j])))
            if len(cand) != k:
                continue
            if all(tuple(sub) in prev_set for sub in combinations(cand, k - 1)):
                candidates.add(cand)

    return sorted(candidates)


def compute_gt_dense_cells_3d(
    occ_cells: list[tuple],
    T: int, X: int, Y: int,
    Wt: int, Wx: int, Wy: int,
    theta: int,
) -> set[tuple]:
    """3D: support_surface[l, sx, sy] >= theta となる窓スタート位置を返す。"""
    if not occ_cells:
        return set()

    G = np.zeros((T, X, Y), dtype=np.int32)
    for (t, x, y) in occ_cells:
        if 0 <= t < T and 0 <= x < X and 0 <= y < Y:
            G[t, x, y] = 1

    psum = np.zeros((T + Wt, X + Wx, Y + Wy), dtype=np.int32)
    psum[Wt:, Wx:, Wy:] = G
    psum = psum.cumsum(0).cumsum(1).cumsum(2)

    l_hi = np.arange(Wt, T + Wt)
    l_lo = np.arange(T)
    x_hi = np.arange(Wx, X + Wx)
    x_lo = np.arange(X)
    y_hi = np.arange(Wy, Y + Wy)
    y_lo = np.arange(Y)

    wsum = (psum[np.ix_(l_hi, x_hi, y_hi)]
            - psum[np.ix_(l_lo, x_hi, y_hi)]
            - psum[np.ix_(l_hi, x_lo, y_hi)]
            - psum[np.ix_(l_hi, x_hi, y_lo)]
            + psum[np.ix_(l_lo, x_lo, y_hi)]
            + psum[np.ix_(l_lo, x_hi, y_lo)]
            + psum[np.ix_(l_hi, x_lo, y_lo)]
            - psum[np.ix_(l_lo, x_lo, y_lo)])

    dense_locs = np.argwhere(wsum >= theta)
    return {(int(r[0]), int(r[1]), int(r[2])) for r in dense_locs}


def compute_gt_dense_cells_4d(
    occ_cells: list[tuple],
    dim_sizes: list[int],
    window: list[int],
    theta: int,
) -> set[tuple]:
    """4D: support_surface >= theta となる窓スタート位置を返す (包除原理)。"""
    if not occ_cells:
        return set()
    d = 4
    G = np.zeros(dim_sizes, dtype=np.int32)
    for cell in occ_cells:
        if all(0 <= cell[k] < dim_sizes[k] for k in range(d)):
            G[tuple(cell)] = 1

    Ws = window
    padded_shape = [dim_sizes[k] + Ws[k] for k in range(d)]
    psum = np.zeros(padded_shape, dtype=np.int32)
    slices = tuple(slice(Ws[k], None) for k in range(d))
    psum[slices] = G
    for k in range(d):
        psum = psum.cumsum(k)

    # 包除原理で窓和を計算
    # shape of result: dim_sizes[0] x dim_sizes[1] x ... x dim_sizes[d-1]
    result_shape = dim_sizes
    wsum = np.zeros(result_shape, dtype=np.int32)

    # 2^d コーナーの符号付き和
    for mask in range(1 << d):
        sign = (-1) ** bin(mask).count('1')
        idx = []
        for k in range(d):
            if mask & (1 << k):
                # low corner: arange(dim_sizes[k])
                idx.append(np.arange(dim_sizes[k]))
            else:
                # high corner: arange(Ws[k], dim_sizes[k] + Ws[k])
                idx.append(np.arange(Ws[k], dim_sizes[k] + Ws[k]))
        wsum += sign * psum[np.ix_(*idx)]

    dense_locs = np.argwhere(wsum >= theta)
    return {tuple(int(r[k]) for k in range(d)) for r in dense_locs}


def compute_gt_dense_cells_for_pattern(
    pattern: tuple[int, ...],
    item_cells_map: dict[int, set[tuple]],
    n_dims: int,
    dim_sizes: list[int],
    window: list[int],
    theta: int,
    occ_cache: dict[tuple[int, ...], set[tuple]] | None = None,
) -> set[tuple]:
    occ_list = list(intersect_item_cells(pattern, item_cells_map, occ_cache))
    if n_dims == 3:
        return compute_gt_dense_cells_3d(
            occ_list,
            dim_sizes[0],
            dim_sizes[1],
            dim_sizes[2],
            window[0],
            window[1],
            window[2],
            theta,
        )
    return compute_gt_dense_cells_4d(occ_list, dim_sizes, window, theta)


def build_exact_gt_regions(
    patterns: list[tuple[int, ...]],
    item_cells_map: dict[int, set[tuple]],
    n_dims: int,
    dim_sizes: list[int],
    window: list[int],
    theta: int,
) -> tuple[dict[tuple, set], int, float]:
    occ_cache: dict[tuple[int, ...], set[tuple]] = {}
    gt_regions: dict[tuple, set] = {}
    total_cells = 0
    t0 = time.perf_counter()
    n_patterns = len(patterns)

    for idx, pattern in enumerate(patterns, 1):
        gt_cells = compute_gt_dense_cells_for_pattern(
            pattern,
            item_cells_map,
            n_dims,
            dim_sizes,
            window,
            theta,
            occ_cache=occ_cache,
        )
        gt_regions[pattern] = gt_cells
        total_cells += len(gt_cells)
        if idx % 500 == 0 or idx == n_patterns:
            elapsed = time.perf_counter() - t0
            print(
                f"    exact GT progress: {idx}/{n_patterns} "
                f"({elapsed:.1f}s, total_cells={total_cells})"
            )

    return gt_regions, total_cells, time.perf_counter() - t0


# ===========================================================================
# 評価指標
# ===========================================================================

def f1_score(pred: set, gt: set) -> dict:
    tp = len(pred & gt)
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(gt) if gt else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
    return {"n_pred": len(pred), "n_tp": tp,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4)}


def jaccard(a: set, b: set) -> float:
    u = len(a | b)
    return len(a & b) / u if u > 0 else 0.0


def mean_jaccard(pred_regions: dict[tuple, set], gt_regions: dict[tuple, set]) -> float:
    if not gt_regions:
        return 0.0
    total = 0.0
    for p, gt_cells in gt_regions.items():
        pred_cells = pred_regions.get(p, set())
        total += jaccard(pred_cells, gt_cells)
    return round(total / len(gt_regions), 4)


# ===========================================================================
# EX-1-1: 比較手法実装
# ===========================================================================

# ---------------------------------------------------------------------------
# Colocation
# ---------------------------------------------------------------------------

def mine_patterns_by_score(
    singleton_items: list[int],
    score_fn,
    threshold: float,
    max_size: int = EX1_MAX_PATTERN_SIZE,
) -> set[tuple[int, ...]]:
    predicted: set[tuple[int, ...]] = {(item,) for item in singleton_items}
    current_level = [(item,) for item in singleton_items]

    while current_level and len(current_level[0]) < max_size:
        next_level = []
        for pattern in generate_apriori_candidates(current_level):
            if score_fn(pattern) >= threshold:
                predicted.add(pattern)
                next_level.append(pattern)
        current_level = next_level

    return predicted


def iter_block_patterns(
    block: dict,
    max_size: int = EX1_MAX_PATTERN_SIZE,
    allowed_items: set[int] | None = None,
):
    items = sorted(
        item for item in block["c_set"]
        if allowed_items is None or item in allowed_items
    )
    for size in range(2, min(max_size, len(items)) + 1):
        yield from combinations(items, size)


def grid_search_colocation(
    cell_items: dict,
    gt_set: set,
    min_pattern_size: int = 1,
) -> dict:
    t0 = time.perf_counter()
    item_cells_map = build_item_cells_map(cell_items)
    singleton_items = sorted(item_cells_map)
    occ_cache: dict[tuple[int, ...], set[tuple]] = {}
    score_cache: dict[tuple[int, ...], float] = {}

    def pi_score(pattern: tuple[int, ...]) -> float:
        if pattern in score_cache:
            return score_cache[pattern]
        occ = intersect_item_cells(pattern, item_cells_map, occ_cache)
        if not occ:
            score = 0.0
        else:
            score = min(len(occ) / len(item_cells_map[item]) for item in pattern)
        score_cache[pattern] = score
        return score

    best = {"f1": -1.0}
    for tau in COLOC_TAU_GRID:
        pred_all = mine_patterns_by_score(
            singleton_items,
            pi_score,
            tau,
            max_size=EX1_MAX_PATTERN_SIZE,
        )
        pred = {
            pattern
            for pattern in pred_all
            if len(pattern) >= min_pattern_size
        }
        ev = f1_score(pred, gt_set)
        if ev["f1"] > best["f1"]:
            best = {"tau": tau, **ev}

    elapsed = time.perf_counter() - t0
    return {"method": "Colocation", "elapsed_s": round(elapsed, 3), "best": best}


# ---------------------------------------------------------------------------
# STCP-Miner
# ---------------------------------------------------------------------------

def grid_search_stcp(
    cell_items: dict,
    gt_set: set,
    T: int,
    min_pattern_size: int = 1,
) -> dict:
    t0 = time.perf_counter()
    all_singletons = sorted({
        int(item)
        for items in cell_items.values()
        for item in items
    })
    best = {"f1": -1.0}

    for Wt in STCP_WINDOW_GRID:
        n_slices = max(1, T // Wt)
        slice_item_maps: list[dict[int, set[tuple]]] = []
        for s in range(n_slices):
            tlo, thi = s * Wt, min((s + 1) * Wt, T)
            item_slice: dict[int, set] = defaultdict(set)
            for cell, items in cell_items.items():
                if tlo <= cell[0] < thi:
                    for i in items:
                        item_slice[i].add(cell)
            slice_item_maps.append({item: set(cells) for item, cells in item_slice.items()})
        occ_caches = [dict() for _ in range(n_slices)]
        score_cache: dict[tuple[int, ...], float] = {}

        def stcp_score(pattern: tuple[int, ...]) -> float:
            if pattern in score_cache:
                return score_cache[pattern]
            best_pi = 0.0
            for item_slice, occ_cache in zip(slice_item_maps, occ_caches):
                if any(item not in item_slice for item in pattern):
                    continue
                occ = intersect_item_cells(pattern, item_slice, occ_cache)
                if not occ:
                    continue
                pi = min(len(occ) / len(item_slice[item]) for item in pattern)
                if pi > best_pi:
                    best_pi = pi
            score_cache[pattern] = best_pi
            return best_pi

        for tau in STCP_TAU_GRID:
            pred_all = mine_patterns_by_score(
                all_singletons,
                stcp_score,
                tau,
                max_size=EX1_MAX_PATTERN_SIZE,
            )
            pred = {
                pattern
                for pattern in pred_all
                if len(pattern) >= min_pattern_size
            }
            ev = f1_score(pred, gt_set)
            if ev["f1"] > best["f1"]:
                best = {"tau": tau, "window_t": Wt, **ev}

    elapsed = time.perf_counter() - t0
    return {"method": "STCP-Miner", "elapsed_s": round(elapsed, 3), "best": best}


# ---------------------------------------------------------------------------
# MZoom (dD対応)
# ---------------------------------------------------------------------------

def mzoom_greedy_nd(entries: list[tuple], n_dims: int, top_k: int = MZOOM_TOP_K) -> list[dict]:
    """
    M-Zoom greedy for (d spatial dims + 1 item dim) tensor.
    entries: tuples of length (n_dims + 1), last element is item_id.
    """
    if len(entries) < 3:
        return []

    total_dims = n_dims + 1  # spatial dims + item dim
    remaining = list(entries)
    blocks = []

    for _ in range(top_k):
        if len(remaining) < 3:
            break

        dim_counts: list[dict] = [{} for _ in range(total_dims)]
        for e in remaining:
            for d in range(total_dims):
                v = e[d]
                dim_counts[d][v] = dim_counts[d].get(v, 0) + 1

        cur_sets: list[set] = [set(dc.keys()) for dc in dim_counts]
        cur_counts: list[dict] = [{k: v for k, v in dc.items()} for dc in dim_counts]
        cur_mass = len(remaining)

        def density(mass: int) -> float:
            sizes = [len(s) for s in cur_sets]
            vol = math.prod(sizes)
            return mass / (vol ** (1.0 / total_dims)) if vol > 0 else 0.0

        best_d = density(cur_mass)
        best_sets_snap = [frozenset(s) for s in cur_sets]

        total_steps = sum(max(0, len(s) - 1) for s in cur_sets)
        for step in range(total_steps):
            best_remove = None
            best_remove_density = -1.0
            for d in range(total_dims):
                if len(cur_sets[d]) <= 1:
                    continue
                min_val = min(cur_counts[d], key=lambda k: cur_counts[d][k])
                new_mass = cur_mass - cur_counts[d][min_val]
                new_sizes = [len(cur_sets[dd]) - (1 if dd == d else 0) for dd in range(total_dims)]
                vol = math.prod(new_sizes)
                new_d = new_mass / (vol ** (1.0 / total_dims)) if vol > 0 else 0.0
                if new_d > best_remove_density:
                    best_remove_density = new_d
                    best_remove = (d, min_val, cur_counts[d][min_val])

            if best_remove is None:
                break
            d, min_val, removed = best_remove
            cur_mass -= removed
            cur_sets[d].discard(min_val)
            del cur_counts[d][min_val]

            if cur_mass < 3:
                break

            cur_d = density(cur_mass)
            if cur_d > best_d:
                best_d = cur_d
                best_sets_snap = [frozenset(s) for s in cur_sets]

        c_set = set(best_sets_snap[-1])  # last dim = item dim
        block = {
            "spatial_sets": [set(best_sets_snap[d]) for d in range(n_dims)],
            "c_set": c_set,
            "pattern": tuple(sorted(c_set)),
            "density": best_d,
            "n_entries": cur_mass,
        }
        blocks.append(block)

        remaining = [
            e for e in remaining
            if not (all(e[d] in best_sets_snap[d] for d in range(n_dims))
                    and e[n_dims] in best_sets_snap[n_dims])
        ]

    return blocks


def collect_mzoom_blocks_nd(cell_items: dict[tuple, frozenset],
                             n_dims: int, top_k: int = MZOOM_TOP_K) -> list[dict]:
    entries = [
        tuple(list(cell) + [c])
        for cell, items in cell_items.items()
        for c in items
    ]
    if len(entries) > MZOOM_MAX_ENTRIES:
        random.seed(42)
        entries = random.sample(entries, MZOOM_MAX_ENTRIES)
    return mzoom_greedy_nd(entries, n_dims=n_dims, top_k=top_k)


def grid_search_mzoom_f1(blocks: list[dict], gt_set: set) -> dict:
    sorted_blocks = sorted(blocks, key=lambda b: -b["density"])
    best = {"f1": -1.0}
    allowed_items = {pattern[0] for pattern in gt_set if len(pattern) == 1}
    pred = {(item,) for item in allowed_items}
    for k in range(1, len(sorted_blocks) + 1):
        pred.update(
            iter_block_patterns(
                sorted_blocks[k - 1],
                max_size=EX1_MAX_PATTERN_SIZE,
                allowed_items=allowed_items,
            )
        )
        ev = f1_score(pred, gt_set)
        if ev["f1"] > best["f1"]:
            best = {"n_blocks": k, "min_density": round(sorted_blocks[k-1]["density"], 4), **ev}
    return best


MAX_BLOCK_POSITIONS = 200_000  # Cartesian product サイズ上限


def compute_position_strides(dim_sizes: list[int]) -> list[int]:
    strides = [1] * len(dim_sizes)
    for idx in range(len(dim_sizes) - 2, -1, -1):
        strides[idx] = strides[idx + 1] * dim_sizes[idx + 1]
    return strides


def positions_to_bitset(positions: set[tuple], strides: list[int]) -> int:
    bits = 0
    for pos in positions:
        idx = 0
        for coord, stride in zip(pos, strides):
            idx += coord * stride
        bits |= 1 << idx
    return bits


def block_to_window_positions_3d(b: dict, n_dims: int = 3) -> set[tuple]:
    """MZoom ブロックから窓スタート位置集合を返す（全空間次元の直積）。"""
    from itertools import product as iproduct
    spatial = [b["spatial_sets"][d] for d in range(n_dims)]
    total = 1
    for s in spatial:
        total *= len(s)
    if total > MAX_BLOCK_POSITIONS:
        # サイズが大きすぎる場合はランダムサブサンプリング
        import random as _rand
        rng = _rand.Random(42)
        result = set()
        for _ in range(MAX_BLOCK_POSITIONS):
            pos = tuple(rng.choice(list(s)) for s in spatial)
            result.add(pos)
        return result
    return set(iproduct(*spatial))


def block_to_window_bitset(b: dict, strides: list[int], n_dims: int = 3) -> int:
    from itertools import product as iproduct

    spatial = [list(b["spatial_sets"][d]) for d in range(n_dims)]
    total = 1
    for s in spatial:
        total *= len(s)

    def encode(pos: tuple[int, ...]) -> int:
        idx = 0
        for coord, stride in zip(pos, strides):
            idx += coord * stride
        return idx

    bits = 0
    if total > MAX_BLOCK_POSITIONS:
        import random as _rand

        rng = _rand.Random(42)
        for _ in range(MAX_BLOCK_POSITIONS):
            pos = tuple(rng.choice(s) for s in spatial)
            bits |= 1 << encode(pos)
        return bits

    for pos in iproduct(*spatial):
        bits |= 1 << encode(pos)
    return bits


def grid_search_mzoom_jaccard(blocks: list[dict],
                               gt_region_bits: dict[tuple, int],
                               strides: list[int],
                               n_dims: int = 3) -> dict:
    sorted_blocks = sorted(blocks, key=lambda b: -b["density"])
    gt_patterns = list(gt_region_bits.keys())
    gt_set = set(gt_patterns)
    gt_pattern_sets = {pattern: set(pattern) for pattern in gt_patterns}

    best = {"mean_jaccard": -1.0}
    pred_region_bits = {pattern: 0 for pattern in gt_patterns}
    pred_set: set[tuple] = set()
    intersections = {pattern: 0 for pattern in gt_patterns}
    unions = {pattern: gt_region_bits[pattern].bit_count() for pattern in gt_patterns}
    jaccard_sum = 0.0
    n_patterns = len(gt_patterns)
    for k in range(1, len(sorted_blocks) + 1):
        b = sorted_blocks[k - 1]
        block_bits = block_to_window_bitset(b, strides, n_dims)
        block_items = b["c_set"]
        for pattern in gt_patterns:
            if not gt_pattern_sets[pattern].issubset(block_items):
                continue

            old_bits = pred_region_bits[pattern]
            added_bits = block_bits & ~old_bits
            if not added_bits:
                continue

            old_union = unions[pattern]
            old_j = intersections[pattern] / old_union if old_union else 0.0
            added_count = added_bits.bit_count()
            added_in_gt = (added_bits & gt_region_bits[pattern]).bit_count()
            intersections[pattern] += added_in_gt
            unions[pattern] += added_count - added_in_gt
            pred_region_bits[pattern] = old_bits | block_bits
            pred_set.add(pattern)
            new_union = unions[pattern]
            new_j = intersections[pattern] / new_union if new_union else 0.0
            jaccard_sum += new_j - old_j

        mj = round(jaccard_sum / n_patterns, 4) if n_patterns else 0.0
        ev = f1_score(pred_set, gt_set)
        if mj > best["mean_jaccard"]:
            best = {
                "n_blocks": k,
                "min_density": round(sorted_blocks[k-1]["density"], 4),
                "mean_jaccard": mj,
                **ev,
            }
    return best


def best_denseblock_f1_across_configs(config_runs: list[dict], gt_set: set) -> dict:
    best = {"f1": -1.0}
    for run in config_runs:
        blocks = run["blocks"]
        if not blocks:
            continue
        cur = grid_search_mzoom_f1(blocks, gt_set)
        cand = {
            **cur,
            "config": run["config"],
            "n_blocks_collected": len(blocks),
            "collect_s": round(run["elapsed_s"], 3),
        }
        if cand["f1"] > best["f1"]:
            best = cand
    return best


def best_denseblock_jaccard_across_configs(
    config_runs: list[dict],
    gt_region_bits: dict[tuple, int],
    strides: list[int],
    n_dims: int,
) -> dict:
    best = {"mean_jaccard": -1.0}
    for run in config_runs:
        blocks = run["blocks"]
        if not blocks:
            continue
        cur = grid_search_mzoom_jaccard(blocks, gt_region_bits, strides, n_dims=n_dims)
        cand = {
            **cur,
            "config": run["config"],
            "n_blocks_collected": len(blocks),
            "collect_s": round(run["elapsed_s"], 3),
        }
        if cand["mean_jaccard"] > best["mean_jaccard"]:
            best = cand
    return best


# ===========================================================================
# EX-1-2: 密集領域比較
# ===========================================================================

# ---------------------------------------------------------------------------
# ST-DBSCAN（自前実装）
# ---------------------------------------------------------------------------

def st_dbscan(cells: list[tuple],
               eps1: float, eps2: float, min_pts: int) -> list[list[tuple]]:
    """ST-DBSCAN: 空間距離 ≤ eps1 かつ 時間距離 ≤ eps2 を隣接条件とする DBSCAN。"""
    n = len(cells)
    if n == 0:
        return []

    arr = np.array(cells, dtype=np.float32)
    t_arr = arr[:, 0]
    xy_arr = arr[:, 1:]

    dt = np.abs(t_arr[:, None] - t_arr[None, :])
    dxy = np.sqrt(((xy_arr[:, None, :] - xy_arr[None, :, :]) ** 2).sum(axis=2))

    adj = (dt <= eps2) & (dxy <= eps1)
    np.fill_diagonal(adj, False)

    neighbor_counts = adj.sum(axis=1)
    core = (neighbor_counts + 1) >= min_pts

    labels = np.full(n, -1, dtype=np.int32)
    cluster_id = 0

    for i in range(n):
        if labels[i] != -1 or not core[i]:
            continue
        q = [i]
        labels[i] = cluster_id
        while q:
            cur = q.pop()
            for nb in np.where(adj[cur])[0]:
                if labels[nb] == -1:
                    labels[nb] = cluster_id
                    if core[nb]:
                        q.append(int(nb))
        cluster_id += 1

    clusters: dict[int, list] = defaultdict(list)
    for i, lbl in enumerate(labels):
        if lbl >= 0:
            clusters[lbl].append(tuple(int(v) for v in cells[i]))
    return list(clusters.values())


def occ_to_window_positions(
    clusters_cells: list[list[tuple]], window: list[int], dim_sizes: list[int]
) -> set[tuple]:
    """クラスタ内セルから、その周辺の窓スタート位置を生成。"""
    n_dims = len(window)
    pred = set()
    for cluster in clusters_cells:
        for cell in cluster:
            ranges = [
                range(max(0, cell[d] - window[d] + 1), cell[d] + 1)
                for d in range(n_dims)
            ]
            from itertools import product as iproduct
            for start in iproduct(*ranges):
                pred.add(start)
    return pred


MAX_STDBSCAN_CELLS = 500


def grid_search_stdbscan(
    occ_cells: list[tuple],
    gt_cells: set[tuple],
    window: list[int],
) -> dict:
    if len(occ_cells) > MAX_STDBSCAN_CELLS:
        random.seed(42)
        occ_sample = random.sample(occ_cells, MAX_STDBSCAN_CELLS)
    else:
        occ_sample = occ_cells

    if len(occ_sample) < 2:
        return {"mean_jaccard": 0.0, "note": "too few cells"}

    arr = np.array(occ_sample, dtype=np.float32)
    t_arr = arr[:, 0]
    xy_arr = arr[:, 1:]
    dt_mat = np.abs(t_arr[:, None] - t_arr[None, :])
    dxy_mat = np.sqrt(((xy_arr[:, None, :] - xy_arr[None, :, :]) ** 2).sum(axis=2))

    best = {"mean_jaccard": -1.0}
    for eps1 in ST_EPS1_GRID:
        for eps2 in ST_EPS2_GRID:
            adj = (dt_mat <= eps2) & (dxy_mat <= eps1)
            np.fill_diagonal(adj, False)
            neighbor_counts = adj.sum(axis=1)

            for min_pts in ST_MINPTS_GRID:
                core = (neighbor_counts + 1) >= min_pts
                labels = np.full(len(occ_sample), -1, dtype=np.int32)
                cluster_id = 0

                for i in range(len(occ_sample)):
                    if labels[i] != -1 or not core[i]:
                        continue
                    q = [i]
                    labels[i] = cluster_id
                    while q:
                        cur = q.pop()
                        for nb in np.where(adj[cur])[0]:
                            if labels[nb] == -1:
                                labels[nb] = cluster_id
                                if core[nb]:
                                    q.append(int(nb))
                    cluster_id += 1

                if cluster_id == 0:
                    continue

                clusters_local = defaultdict(list)
                for i, lbl in enumerate(labels):
                    if lbl >= 0:
                        clusters_local[lbl].append(tuple(int(v) for v in occ_sample[i]))
                clusters_list = list(clusters_local.values())

                pred = occ_to_window_positions(clusters_list, window, [])
                mj_val = jaccard(pred, gt_cells)
                if mj_val > best["mean_jaccard"]:
                    best = {
                        "eps1": eps1, "eps2": eps2, "min_pts": min_pts,
                        "mean_jaccard": round(mj_val, 4),
                        "n_pred": len(pred),
                    }
    return best


def run_stdbscan_fixed(
    occ_cells: list[tuple],
    window: list[int],
    eps1: int = STDBSCAN_FIXED_EPS1,
    eps2: int = STDBSCAN_FIXED_EPS2,
    min_pts: int = STDBSCAN_FIXED_MIN_PTS,
) -> list[list[tuple]]:
    """固定パラメータで ST-DBSCAN を実行してクラスタを返す。"""
    if len(occ_cells) > MAX_STDBSCAN_CELLS:
        random.seed(42)
        occ_cells = random.sample(occ_cells, MAX_STDBSCAN_CELLS)
    return st_dbscan(occ_cells, eps1=eps1, eps2=eps2, min_pts=min_pts)


# ---------------------------------------------------------------------------
# LISA
# ---------------------------------------------------------------------------

def run_lisa_one_pattern(
    occ_cells: list[tuple],
    gt_cells: set[tuple],
    spatial_sizes: list[int],
    weight_type: str = "queen",
) -> dict:
    """
    LISA を 1 パターンに適用（空間 2 次元に投影）。
    """
    try:
        import esda
        import libpysal.weights as w_module
    except ImportError:
        return {"mean_jaccard": 0.0, "note": "esda not installed"}

    # 空間2次元 (dim 1, dim 2) に投影
    X_size = spatial_sizes[1] if len(spatial_sizes) > 1 else 1
    Y_size = spatial_sizes[2] if len(spatial_sizes) > 2 else 1

    density_map = np.zeros((X_size, Y_size), dtype=float)
    for cell in occ_cells:
        x = int(cell[1]) if len(cell) > 1 else 0
        y = int(cell[2]) if len(cell) > 2 else 0
        if 0 <= x < X_size and 0 <= y < Y_size:
            density_map[x, y] += 1

    nonzero = np.argwhere(density_map > 0)
    if len(nonzero) < 4:
        return {"mean_jaccard": 0.0, "note": "too few points"}

    values = np.array([density_map[r[0], r[1]] for r in nonzero])

    try:
        k = 3 if weight_type in ("queen", "rook", "knn3") else 5
        k = min(k, len(nonzero) - 1)
        if k < 1:
            return {"mean_jaccard": 0.0, "note": "too few points"}
        W = w_module.KNN.from_array(nonzero, k=k)
        W.transform = "r"
    except Exception:
        return {"mean_jaccard": 0.0, "note": "weights error"}

    try:
        moran = esda.Moran_Local(values, W, transformation="r", permutations=19)
        sig_hh = (moran.q == 1) & (moran.p_sim < 0.05)
        pred_xy = {(int(nonzero[i][0]), int(nonzero[i][1])) for i in range(len(nonzero)) if sig_hh[i]}
    except Exception:
        return {"mean_jaccard": 0.0, "note": "moran error"}

    gt_xy = {(cell[1], cell[2]) for cell in gt_cells if len(cell) > 2}
    mj_val = jaccard(pred_xy, gt_xy)
    return {
        "mean_jaccard": round(mj_val, 4),
        "n_pred": len(pred_xy),
    }


def grid_search_lisa(
    occ_cells: list[tuple],
    gt_cells: set[tuple],
    spatial_sizes: list[int],
) -> dict:
    best = {"mean_jaccard": -1.0}
    for wt in LISA_WEIGHT_TYPES:
        result = run_lisa_one_pattern(occ_cells, gt_cells, spatial_sizes, weight_type=wt)
        mj = result.get("mean_jaccard", 0.0)
        if mj > best["mean_jaccard"]:
            best = {"weight_type": wt, **result}
    return best


def run_lisa_fixed(
    occ_cells: list[tuple],
    spatial_sizes: list[int],
    weight_type: str = LISA_FIXED_WEIGHT,
) -> bool:
    """固定パラメータで LISA を実行し、High-High ホットスポットが1つ以上あれば True を返す。"""
    try:
        import esda
        import libpysal.weights as w_module
    except ImportError:
        return False

    X_size = spatial_sizes[1] if len(spatial_sizes) > 1 else 1
    Y_size = spatial_sizes[2] if len(spatial_sizes) > 2 else 1

    density_map = np.zeros((X_size, Y_size), dtype=float)
    for cell in occ_cells:
        x = int(cell[1]) if len(cell) > 1 else 0
        y = int(cell[2]) if len(cell) > 2 else 0
        if 0 <= x < X_size and 0 <= y < Y_size:
            density_map[x, y] += 1

    nonzero = np.argwhere(density_map > 0)
    if len(nonzero) < 4:
        return False

    values = np.array([density_map[r[0], r[1]] for r in nonzero])

    try:
        k = 5 if weight_type == "knn5" else 3
        k = min(k, len(nonzero) - 1)
        if k < 1:
            return False
        W = w_module.KNN.from_array(nonzero, k=k)
        W.transform = "r"
        moran = esda.Moran_Local(values, W, transformation="r", permutations=19)
        sig_hh = (moran.q == 1) & (moran.p_sim < 0.05)
        return bool(sig_hh.any())
    except Exception:
        return False


# ===========================================================================
# EX-R1-2: ST-DBSCAN / LISA の mean Jaccard（全 GT パターン）
# ===========================================================================

def eval_stdbscan_mean_jaccard(
    gt_regions: dict[tuple, set],
    item_cells_map: dict[int, set[tuple]],
    window: list[int],
    dim_sizes: list[int],
) -> dict:
    """ST-DBSCAN mean Jaccard over all GT patterns with grid search."""
    occ_cache: dict[tuple[int, ...], set[tuple]] = {}
    n_patterns = len(gt_regions)
    if n_patterns == 0:
        return {"mean_jaccard": 0.0}

    best: dict = {"mean_jaccard": -1.0}

    for eps1 in ST_EPS1_GRID:
        for eps2 in ST_EPS2_GRID:
            for min_pts in ST_MINPTS_GRID:
                total_jacc = 0.0
                for pattern, gt_cells in gt_regions.items():
                    occ = list(intersect_item_cells(pattern, item_cells_map, occ_cache))
                    if not occ:
                        continue
                    if len(occ) > MAX_STDBSCAN_CELLS:
                        random.seed(42)
                        occ_sample = random.sample(occ, MAX_STDBSCAN_CELLS)
                    else:
                        occ_sample = occ
                    if len(occ_sample) < 2:
                        continue
                    clusters = st_dbscan(occ_sample, eps1=eps1, eps2=eps2, min_pts=min_pts)
                    if clusters:
                        pred = occ_to_window_positions(clusters, window, dim_sizes)
                        total_jacc += jaccard(pred, gt_cells)
                mj = round(total_jacc / n_patterns, 4)
                if mj > best["mean_jaccard"]:
                    best = {
                        "eps1": eps1, "eps2": eps2, "min_pts": min_pts,
                        "mean_jaccard": mj,
                    }

    return best


def precompute_lisa_weights(
    dim_sizes: list[int],
    k_values: list[int] = [3, 5],
) -> dict:
    """Precompute KNN weights for the spatial grid (shared across all patterns)."""
    import libpysal.weights as w_module
    from itertools import product as iproduct

    spatial_dims = dim_sizes[1:]
    all_spatial_cells = list(iproduct(*[range(s) for s in spatial_dims]))
    n_spatial = len(all_spatial_cells)
    spatial_arr = np.array(all_spatial_cells, dtype=np.float32)
    cell_to_idx = {c: i for i, c in enumerate(all_spatial_cells)}

    weights = {}
    for k in k_values:
        k_actual = min(k, n_spatial - 1)
        if k_actual < 1:
            continue
        W = w_module.KNN.from_array(spatial_arr, k=k_actual)
        W.transform = "r"
        weights[k] = W

    return {
        "all_spatial_cells": all_spatial_cells,
        "n_spatial": n_spatial,
        "cell_to_idx": cell_to_idx,
        "weights": weights,
    }


def lisa_hotspot_spatial_cells_precomputed(
    occ_cells: list[tuple],
    lisa_pre: dict,
    k: int = 5,
) -> set[tuple]:
    """
    Run LISA using precomputed weights.
    Returns set of hotspot spatial cells (excluding time dimension).
    """
    import esda

    all_spatial_cells = lisa_pre["all_spatial_cells"]
    n_spatial = lisa_pre["n_spatial"]
    W = lisa_pre["weights"].get(k)
    if W is None:
        return set()

    spatial_counts: dict[tuple, int] = defaultdict(int)
    for cell in occ_cells:
        spatial_counts[cell[1:]] += 1

    values = np.array([spatial_counts.get(c, 0) for c in all_spatial_cells], dtype=float)

    if values.sum() == 0 or values.std() == 0:
        return set()

    try:
        moran = esda.Moran_Local(values, W, transformation="r", permutations=99)
        sig_hh = (moran.q == 1) & (moran.p_sim < 0.05)
        return {all_spatial_cells[i] for i in range(n_spatial) if sig_hh[i]}
    except Exception:
        return set()


def eval_lisa_mean_jaccard(
    gt_regions: dict[tuple, set],
    item_cells_map: dict[int, set[tuple]],
    window: list[int],
    dim_sizes: list[int],
    n_dims: int,
) -> dict:
    """LISA mean Jaccard: spatial projection -> hotspots -> expand to d-dim window positions."""
    try:
        import esda  # noqa: F401
        import libpysal  # noqa: F401
    except ImportError:
        return {"mean_jaccard": 0.0, "note": "esda not installed"}

    occ_cache: dict[tuple[int, ...], set[tuple]] = {}
    n_patterns = len(gt_regions)
    if n_patterns == 0:
        return {"mean_jaccard": 0.0}

    # Precompute KNN weights once for this dataset
    print("      LISA: precomputing spatial KNN weights...")
    lisa_pre = precompute_lisa_weights(dim_sizes, k_values=[3, 5])
    print(f"      LISA: spatial grid = {lisa_pre['n_spatial']} cells")

    best: dict = {"mean_jaccard": -1.0}

    for k in [3, 5]:
        if k not in lisa_pre["weights"]:
            continue
        total_jacc = 0.0
        n_done = 0
        for pattern, gt_cells in gt_regions.items():
            occ = list(intersect_item_cells(pattern, item_cells_map, occ_cache))
            if not occ:
                continue

            hotspots = lisa_hotspot_spatial_cells_precomputed(occ, lisa_pre, k=k)
            if not hotspots:
                n_done += 1
                continue

            hotspot_occ = [cell for cell in occ if cell[1:] in hotspots]
            if hotspot_occ:
                pred = occ_to_window_positions([hotspot_occ], window, dim_sizes)
                total_jacc += jaccard(pred, gt_cells)
            n_done += 1
            if n_done % 500 == 0:
                print(f"      LISA k={k}: {n_done}/{n_patterns} done")

        mj = round(total_jacc / n_patterns, 4)
        print(f"      LISA k={k}: mean_jaccard={mj:.4f}")
        if mj > best["mean_jaccard"]:
            best = {"k": k, "mean_jaccard": mj}

    return best


# ===========================================================================
# EX-1-1: ST-DBSCAN / LISA のパターン検出 F1
# ===========================================================================

def eval_stdbscan_f1(
    cell_items: dict[tuple, frozenset],
    gt_set: set,
    window: list[int],
    spatial_sizes: list[int],
    max_patterns: int = MAX_PATTERNS_STDBSCAN_LISA,
) -> dict:
    """
    ST-DBSCAN をパターン検出に適用。
    GT パターン上位 max_patterns について:
      - 少なくとも1クラスタが検出 → detected
    detected / not_detected で F1 を計算。
    """
    t0 = time.perf_counter()

    # アイテム→出現セル マッピング
    item_cells_map: dict[int, set] = defaultdict(set)
    for cell, items in cell_items.items():
        for i in items:
            item_cells_map[i].add(tuple(cell))

    # GT パターンを頻度順でソートして上位 max_patterns に限定
    # gt_set は tuple(sorted items) の set
    gt_list = sorted(gt_set)  # 再現性のため sorted
    # 頻度（共起セル数）でソート
    def cooccurrence_count(p):
        i, j = p[0], p[1]
        return len(item_cells_map[i] & item_cells_map[j])

    gt_sorted = sorted(gt_list, key=cooccurrence_count, reverse=True)
    eval_patterns = gt_sorted[:max_patterns]
    n_eval = len(eval_patterns)

    detected = set()
    for pattern in eval_patterns:
        i, j = pattern[0], pattern[1]
        occ = list(item_cells_map[i] & item_cells_map[j])
        if not occ:
            continue
        clusters = run_stdbscan_fixed(occ, window)
        if len(clusters) > 0:
            detected.add(pattern)

    # F1 計算（eval_patterns のみを対象とする）
    eval_set = set(eval_patterns)
    ev = f1_score(detected, eval_set)
    elapsed = time.perf_counter() - t0

    return {
        "method": "ST-DBSCAN",
        "elapsed_s": round(elapsed, 3),
        "n_eval_patterns": n_eval,
        "n_full_gt": len(gt_set),
        "eps1": STDBSCAN_FIXED_EPS1,
        "eps2": STDBSCAN_FIXED_EPS2,
        "min_pts": STDBSCAN_FIXED_MIN_PTS,
        "best": ev,
    }


def eval_lisa_f1(
    cell_items: dict[tuple, frozenset],
    gt_set: set,
    spatial_sizes: list[int],
    max_patterns: int = MAX_PATTERNS_STDBSCAN_LISA,
) -> dict:
    """
    LISA をパターン検出に適用。
    GT パターン上位 max_patterns について:
      - High-High ホットスポットが1つ以上あれば → detected
    detected / not_detected で F1 を計算。
    """
    t0 = time.perf_counter()

    item_cells_map: dict[int, set] = defaultdict(set)
    for cell, items in cell_items.items():
        for i in items:
            item_cells_map[i].add(tuple(cell))

    def cooccurrence_count(p):
        i, j = p[0], p[1]
        return len(item_cells_map[i] & item_cells_map[j])

    gt_list = sorted(gt_set)
    gt_sorted = sorted(gt_list, key=cooccurrence_count, reverse=True)
    eval_patterns = gt_sorted[:max_patterns]
    n_eval = len(eval_patterns)

    detected = set()
    for pattern in eval_patterns:
        i, j = pattern[0], pattern[1]
        occ = list(item_cells_map[i] & item_cells_map[j])
        if not occ:
            continue
        has_hh = run_lisa_fixed(occ, spatial_sizes)
        if has_hh:
            detected.add(pattern)

    eval_set = set(eval_patterns)
    ev = f1_score(detected, eval_set)
    elapsed = time.perf_counter() - t0

    return {
        "method": "LISA",
        "elapsed_s": round(elapsed, 3),
        "n_eval_patterns": n_eval,
        "n_full_gt": len(gt_set),
        "weight_type": LISA_FIXED_WEIGHT,
        "best": ev,
    }


# ===========================================================================
# メイン: EX-1-1 と EX-1-2
# ===========================================================================

def run_ex1_dataset(ds_name: str, run_ex12: bool = True) -> dict:
    cfg = DATASETS[ds_name]
    n_dims = cfg["n_dims"]
    window_str = cfg["window"]
    window = [int(x) for x in window_str.split(",")]
    theta = cfg["threshold"]

    print(f"\n{'='*70}")
    print(f"EX-1: {ds_name} (W={window_str}, θ={theta}, dims={n_dims}, |P|<= {EX1_MAX_PATTERN_SIZE})")
    print(f"{'='*70}")

    # メタデータ
    if cfg["meta"].exists():
        meta = load_meta(cfg["meta"])
        print(f"  グリッド: {meta.get('grid_dims', meta.get('dims', '?'))}")
    else:
        meta = {}
        print("  メタデータなし")

    # データ読み込み
    print("  データ読み込み中...")
    t_load = time.perf_counter()
    if n_dims == 3:
        cell_items, T, X, Y, n_cells = load_tsv(cfg["tsv"])
        dim_sizes = [T, X, Y]
        spatial_sizes = dim_sizes
    else:
        cell_items, dim_sizes, n_cells = load_tsv_nd(cfg["tsv"], n_dims)
        spatial_sizes = dim_sizes
        T = dim_sizes[0]
    print(f"    → {n_cells} セル, dim_sizes={dim_sizes}  ({time.perf_counter()-t_load:.2f}s)")

    # GT 取得
    print("  GT (md_pipeline) 実行中...")
    gt_patterns, t_aw = run_md_pipeline(
        cfg["tsv"],
        window_str,
        theta,
        n_dims=n_dims,
        max_length=EX1_MAX_PATTERN_SIZE,
    )
    gt_set = set(gt_patterns.keys())
    gt_size_hist = defaultdict(int)
    for pattern in gt_set:
        gt_size_hist[len(pattern)] += 1
    print(f"    → |P*| = {len(gt_set)} パターン  ({t_aw:.3f}s)")
    print(f"      size breakdown: {dict(sorted(gt_size_hist.items()))}")

    item_cells_map = build_item_cells_map(cell_items)

    result = {
        "dataset": ds_name,
        "settings": {
            "window": window_str,
            "threshold": theta,
            "n_dims": n_dims,
            "max_pattern_size": EX1_MAX_PATTERN_SIZE,
        },
        "gt_n_patterns": len(gt_set),
        "gt_elapsed_s": round(t_aw, 4),
        "dim_sizes": dim_sizes,
        "gt_size_hist": dict(sorted(gt_size_hist.items())),
    }

    # ---- EX-1-1 ----
    print("\n  === EX-1-1: パターン検出 F1 ===")

    # ---- Colocation ----
    print("  [Colocation] グリッドサーチ中...")
    t0 = time.perf_counter()
    gs_coloc = grid_search_colocation(cell_items, gt_set)
    print(f"    最良: F1={gs_coloc['best']['f1']:.3f} "
          f"(P={gs_coloc['best']['precision']:.3f}, R={gs_coloc['best']['recall']:.3f}) "
          f"τ={gs_coloc['best']['tau']}  ({time.perf_counter()-t0:.2f}s)")
    result["colocation"] = gs_coloc

    # ---- STCP-Miner ----
    print("  [STCP-Miner] グリッドサーチ中...")
    t0 = time.perf_counter()
    gs_stcp = grid_search_stcp(cell_items, gt_set, T)
    print(f"    最良: F1={gs_stcp['best']['f1']:.3f} "
          f"τ={gs_stcp['best'].get('tau', '?')}, Wt={gs_stcp['best'].get('window_t', '?')}  "
          f"({time.perf_counter()-t0:.2f}s)")
    result["stcp_miner"] = gs_stcp

    denseblock_runs: dict[str, list[dict]] = {}

    # ---- M-Zoom ----
    mzoom_runs = []
    for dm in MZOOM_DENSITY_MEASURES:
        print(f"  [M-Zoom] 公式実装でブロック収集中 (dm={dm}, top_k={MZOOM_TOP_K}, n_dims={n_dims})...")
        t0 = time.perf_counter()
        mzoom_blocks = collect_mzoom_blocks_official(cell_items, n_dims=n_dims, top_k=MZOOM_TOP_K, density_measure=dm)
        t_collect = time.perf_counter() - t0
        mzoom_runs.append({
            "config": {"density_measure": dm},
            "blocks": mzoom_blocks,
            "elapsed_s": t_collect,
        })
        print(f"    dm={dm}: {len(mzoom_blocks)} blocks ({t_collect:.2f}s)")
    denseblock_runs["mzoom"] = mzoom_runs
    mzoom_best_f1 = best_denseblock_f1_across_configs(mzoom_runs, gt_set)
    print(f"    F1 最良: F1={mzoom_best_f1['f1']:.3f} "
          f"(P={mzoom_best_f1['precision']:.3f}, R={mzoom_best_f1['recall']:.3f}) "
          f"k={mzoom_best_f1['n_blocks']} dm={mzoom_best_f1['config']}  ")
    result["mzoom"] = {
        "method": "M-Zoom",
        "best": mzoom_best_f1,
    }

    # ---- M-Biz ----
    mbiz_runs = []
    for dm in MZOOM_DENSITY_MEASURES:
        print(f"  [M-Biz] 公式実装でブロック収集中 (dm={dm}, top_k={MZOOM_TOP_K}, n_dims={n_dims})...")
        t0 = time.perf_counter()
        mbiz_blocks = collect_mbiz_blocks_official(cell_items, n_dims=n_dims, top_k=MZOOM_TOP_K, density_measure=dm)
        t_collect = time.perf_counter() - t0
        mbiz_runs.append({
            "config": {"density_measure": dm},
            "blocks": mbiz_blocks,
            "elapsed_s": t_collect,
        })
        print(f"    dm={dm}: {len(mbiz_blocks)} blocks ({t_collect:.2f}s)")
    denseblock_runs["mbiz"] = mbiz_runs
    mbiz_best_f1 = best_denseblock_f1_across_configs(mbiz_runs, gt_set)
    print(f"    F1 最良: F1={mbiz_best_f1['f1']:.3f} "
          f"(P={mbiz_best_f1['precision']:.3f}, R={mbiz_best_f1['recall']:.3f}) "
          f"k={mbiz_best_f1['n_blocks']} dm={mbiz_best_f1['config']}  ")
    result["mbiz"] = {
        "method": "M-Biz",
        "best": mbiz_best_f1,
    }

    # ---- D-Cube ----
    print("  [D-Cube] 公式実装グリッドサーチ中...")
    dcube_runs = []
    for dm in MZOOM_DENSITY_MEASURES:
        for policy in DCUBE_POLICY_GRID:
            for mass_threshold in DCUBE_MASS_THRESHOLD_GRID:
                t0 = time.perf_counter()
                blocks = collect_dcube_blocks_official(
                    cell_items,
                    n_dims=n_dims,
                    top_k=MZOOM_TOP_K,
                    density_measure=dm,
                    policy=policy,
                    mass_threshold=mass_threshold,
                )
                dcube_runs.append({
                    "config": {
                        "density_measure": dm,
                        "policy": policy,
                        "mass_threshold": mass_threshold,
                    },
                    "blocks": blocks,
                    "elapsed_s": time.perf_counter() - t0,
                })
                print(f"    dm={dm}, policy={policy}, theta={mass_threshold}: {len(blocks)} blocks")
    denseblock_runs["dcube"] = dcube_runs
    dcube_best_f1 = best_denseblock_f1_across_configs(dcube_runs, gt_set)
    print(f"    F1 最良: F1={dcube_best_f1['f1']:.3f} "
          f"(P={dcube_best_f1['precision']:.3f}, R={dcube_best_f1['recall']:.3f}) "
          f"cfg={dcube_best_f1['config']} k={dcube_best_f1['n_blocks']}")
    result["dcube"] = {
        "method": "D-Cube",
        "best": dcube_best_f1,
    }

    # ---- CatchCore ----
    print("  [CatchCore] 公式実装グリッドサーチ中...")
    catchcore_runs = []
    for hs in CATCHCORE_HS_GRID:
        for p in CATCHCORE_P_GRID:
            for cons in CATCHCORE_CONS_GRID:
                for etas in CATCHCORE_ETAS_GRID:
                    t0 = time.perf_counter()
                    blocks = collect_catchcore_blocks_official(
                        cell_items,
                        n_dims=n_dims,
                        hs=hs,
                        p=p,
                        cons=cons,
                        etas=etas,
                    )
                    catchcore_runs.append({
                        "config": {
                            "hs": hs,
                            "p": p,
                            "cons": cons,
                            "etas": etas,
                        },
                        "blocks": blocks,
                        "elapsed_s": time.perf_counter() - t0,
                    })
                    print(f"    hs={hs}, p={p}, cons={cons}, etas={etas}: {len(blocks)} levels")
    denseblock_runs["catchcore"] = catchcore_runs
    catchcore_best_f1 = best_denseblock_f1_across_configs(catchcore_runs, gt_set)
    print(f"    F1 最良: F1={catchcore_best_f1['f1']:.3f} "
          f"(P={catchcore_best_f1['precision']:.3f}, R={catchcore_best_f1['recall']:.3f}) "
          f"cfg={catchcore_best_f1['config']} k={catchcore_best_f1['n_blocks']}")
    result["catchcore"] = {
        "method": "CatchCore",
        "best": catchcore_best_f1,
    }

    # ---- EX-1-2: 密集領域復元 ----
    if run_ex12:
        print("\n  === EX-1-2: 密集領域復元 ===")
        gt_pattern_list = sorted(gt_patterns.keys(), key=lambda p: (len(p), p))
        print(f"  全 GT パターン {len(gt_pattern_list)} 件の exact dense-start 集合を構築中...")
        gt_regions, total_gt_cells, gt_regions_elapsed = build_exact_gt_regions(
            gt_pattern_list,
            item_cells_map,
            n_dims,
            dim_sizes,
            window,
            theta,
        )
        strides = compute_position_strides(dim_sizes)
        print("    GT 密集セルを bitset 化中...")
        gt_region_bits = {
            pattern: positions_to_bitset(cells, strides)
            for pattern, cells in gt_regions.items()
        }
        result["jaccard_eval_n_patterns"] = len(gt_regions)
        result["jaccard_gt_total_cells"] = total_gt_cells
        result["jaccard_gt_elapsed_s"] = round(gt_regions_elapsed, 4)
        print(
            f"    GT 密集セル構築完了 "
            f"({len(gt_regions)} patterns, {total_gt_cells} total cells, {gt_regions_elapsed:.2f}s)"
        )

        for method_key, label in [
            ("mzoom", "M-Zoom"),
            ("mbiz", "M-Biz"),
            ("dcube", "D-Cube"),
            ("catchcore", "CatchCore"),
        ]:
            print(f"  [{label}] Jaccard グリッドサーチ...")
            t0 = time.perf_counter()
            best_jacc = best_denseblock_jaccard_across_configs(
                denseblock_runs[method_key],
                gt_region_bits,
                strides,
                n_dims=n_dims,
            )
            print(f"    mean Jaccard={best_jacc['mean_jaccard']:.3f} "
                  f"cfg={best_jacc.get('config', {})} "
                  f"({time.perf_counter()-t0:.2f}s)")
            result[method_key]["best_jaccard"] = best_jacc

        # ---- ST-DBSCAN (oracle pattern → region) ----
        print("  [ST-DBSCAN] mean Jaccard グリッドサーチ中...")
        t0 = time.perf_counter()
        stdb_jacc = eval_stdbscan_mean_jaccard(
            gt_regions, item_cells_map, window, dim_sizes,
        )
        t_stdb = time.perf_counter() - t0
        print(f"    mean Jaccard={stdb_jacc['mean_jaccard']:.4f} "
              f"eps1={stdb_jacc.get('eps1')}, eps2={stdb_jacc.get('eps2')}, "
              f"min_pts={stdb_jacc.get('min_pts')}  ({t_stdb:.1f}s)")
        result["stdbscan"] = {
            "method": "ST-DBSCAN",
            "best_jaccard": stdb_jacc,
            "elapsed_s": round(t_stdb, 3),
        }

        # ---- LISA (oracle pattern → region) ----
        print("  [LISA] mean Jaccard 評価中...")
        t0 = time.perf_counter()
        lisa_jacc = eval_lisa_mean_jaccard(
            gt_regions, item_cells_map, window, dim_sizes, n_dims,
        )
        t_lisa = time.perf_counter() - t0
        print(f"    mean Jaccard={lisa_jacc['mean_jaccard']:.4f} "
              f"k={lisa_jacc.get('k')}  ({t_lisa:.1f}s)")
        result["lisa"] = {
            "method": "LISA",
            "best_jaccard": lisa_jacc,
            "elapsed_s": round(t_lisa, 3),
        }

    return result


# ===========================================================================
# エントリポイント
# ===========================================================================

def main():
    print("=" * 70)
    print("EX-1 v2: 比較実験（全4データセット）")
    print("=" * 70)

    all_results = {}

    out_file = OUT_DIR / "ex1_v2_results.json"

    for ds_name in ["chicago", "nypd", "nyc_311", "usgs_eq"]:
        ds_t0 = time.perf_counter()
        try:
            all_results[ds_name] = run_ex1_dataset(ds_name, run_ex12=True)
        except Exception as e:
            print(f"\nERROR: {ds_name}: {e}")
            import traceback; traceback.print_exc()
            all_results[ds_name] = {"dataset": ds_name, "error": str(e)}
        ds_elapsed = time.perf_counter() - ds_t0
        print(f"\n  [{ds_name} 完了: {ds_elapsed:.1f}s]")

        # 各データセット完了後に中間保存
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
        print(f"  中間保存: {out_file}")

    print(f"\n全結果保存: {out_file}")

    # サマリ表示
    print("\n" + "=" * 70)
    print("EX-1-1 サマリ（F1 最良値）")
    ds_names = list(all_results.keys())
    header = f"{'手法':<15}" + "".join(f"{ds:>12}" for ds in ds_names)
    print(header)
    print("-" * (15 + 12 * len(ds_names)))

    method_map = [
        ("colocation",   "Colocation",  lambda r: r.get("colocation", {}).get("best", {}).get("f1", "---")),
        ("stcp_miner",   "STCP-Miner",  lambda r: r.get("stcp_miner", {}).get("best", {}).get("f1", "---")),
        ("mzoom",        "MZoom",       lambda r: r.get("mzoom", {}).get("best", {}).get("f1", "---")),
        ("mbiz",         "M-Biz",       lambda r: r.get("mbiz", {}).get("best", {}).get("f1", "---")),
        ("dcube",        "D-Cube",      lambda r: r.get("dcube", {}).get("best", {}).get("f1", "---")),
        ("catchcore",    "CatchCore",   lambda r: r.get("catchcore", {}).get("best", {}).get("f1", "---")),
    ]
    for _, label, getter in method_map:
        row = f"  {label:<13}" + "".join(f"{str(getter(all_results.get(ds, {}))):>12}" for ds in ds_names)
        print(row)

    print("\nEX-1-2 サマリ（mean Jaccard 最良値）")
    header2 = f"{'手法':<15}" + "".join(f"{ds:>12}" for ds in ds_names)
    print(header2)
    print("-" * (15 + 12 * len(ds_names)))

    method_map2 = [
        ("mzoom",         "MZoom",      lambda r: r.get("mzoom", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
        ("mbiz",          "M-Biz",      lambda r: r.get("mbiz", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
        ("dcube",         "D-Cube",     lambda r: r.get("dcube", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
        ("catchcore",     "CatchCore",  lambda r: r.get("catchcore", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
        ("stdbscan",      "ST-DBSCAN",  lambda r: r.get("stdbscan", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
        ("lisa",          "LISA",        lambda r: r.get("lisa", {}).get("best_jaccard", {}).get("mean_jaccard", "---")),
    ]
    for _, label, getter in method_map2:
        row = f"  {label:<13}" + "".join(f"{str(getter(all_results.get(ds, {}))):>12}" for ds in ds_names)
        print(row)


if __name__ == "__main__":
    main()
