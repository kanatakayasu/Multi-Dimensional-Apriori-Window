//! Multi-Dimensional Apriori-Window.
//!
//! For each fixed spatial origin, occurrences inside the spatial window are collapsed
//! into a temporal multiset and the 1-D dense-interval solver is applied directly.
//! Output is stored as `spatial_start -> [time_interval, ...]` rather than dense cells.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

use itertools::Itertools;
use apriori_window_1d::{
    compute_dense_intervals_multiset, compute_dense_intervals_with_candidates_multiset,
    intersect_interval_lists, lower_bound, upper_bound,
};

// ---------------------------------------------------------------------------
// Apriori candidate generation and pruning
// ---------------------------------------------------------------------------

pub fn generate_candidates(prev_frequents: &[Vec<i64>], k: usize) -> Vec<Vec<i64>> {
    let mut prev_sorted = prev_frequents.to_vec();
    prev_sorted.sort();
    let mut candidates = BTreeSet::new();

    for i in 0..prev_sorted.len() {
        for j in (i + 1)..prev_sorted.len() {
            if k > 2 && prev_sorted[i][..k - 2] != prev_sorted[j][..k - 2] {
                break;
            }
            let mut candidate = prev_sorted[i].clone();
            for item in &prev_sorted[j] {
                if !candidate.contains(item) {
                    candidate.push(*item);
                }
            }
            candidate.sort_unstable();
            if candidate.len() == k {
                candidates.insert(candidate);
            }
        }
    }

    candidates.into_iter().collect()
}

pub fn prune_candidates(
    candidates: Vec<Vec<i64>>,
    prev_frequents_set: &HashSet<Vec<i64>>,
) -> Vec<Vec<i64>> {
    candidates
        .into_iter()
        .filter(|candidate| {
            candidate
                .iter()
                .cloned()
                .combinations(candidate.len() - 1)
                .all(|subset| prev_frequents_set.contains(&subset))
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Parameters and input types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Md3DParams {
    pub bin_sizes: (f64, f64, f64),
    pub window_bins: (usize, usize, usize),
    pub threshold: usize,
    pub max_length: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct Txn3D {
    pub ti: usize,
    pub xi: usize,
    pub yi: usize,
    pub items: Vec<i64>,
}

#[derive(Debug, Clone)]
pub struct MdNDParams {
    pub bin_sizes: Vec<f64>,
    pub window_bins: Vec<usize>,
    pub threshold: usize,
    pub max_length: Option<usize>,
    /// Retained for compatibility; unused in the interval-based implementation.
    pub use_prefix_sum: bool,
    /// Retained for compatibility; unused in the interval-based implementation.
    pub use_binsearch: bool,
    /// When false, uses naive t-axis scan instead of stride-based solver.
    pub use_t_stride: bool,
    /// When false, skips (k-1)-subset interval map candidate pruning.
    pub use_apriori_prune: bool,
}

impl Default for MdNDParams {
    fn default() -> Self {
        Self {
            bin_sizes: vec![1.0],
            window_bins: vec![5],
            threshold: 3,
            max_length: None,
            use_prefix_sum: false,
            use_binsearch: true,
            use_t_stride: true,
            use_apriori_prune: true,
        }
    }
}

#[derive(Debug, Clone)]
pub struct TxnND {
    pub coords: Vec<usize>,
    pub items: Vec<i64>,
}

pub type DenseTimeInterval = (usize, usize);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DenseRegion {
    pub spatial_start: Vec<usize>,
    pub intervals: Vec<DenseTimeInterval>,
}

pub type DenseRegionND = DenseRegion;

type IntervalMapND = BTreeMap<Vec<usize>, Vec<(i64, i64)>>;

// ---------------------------------------------------------------------------
// Discretization
// ---------------------------------------------------------------------------

pub fn discretize(
    raw: &[(f64, f64, f64, Vec<i64>)],
    params: &Md3DParams,
) -> (Vec<Txn3D>, (usize, usize, usize)) {
    if raw.is_empty() {
        return (Vec::new(), (1, 1, 1));
    }

    let (dt, dx, dy) = params.bin_sizes;
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
                .map(|(coord, &bin_size)| (coord / bin_size).floor() as usize)
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
// Interval output helpers
// ---------------------------------------------------------------------------

fn effective_window_size(wt_bins: usize) -> i64 {
    if wt_bins == 0 {
        panic!("Wt must be >= 1");
    }
    (wt_bins - 1) as i64
}

fn to_usize_intervals(intervals: &[(i64, i64)]) -> Vec<DenseTimeInterval> {
    intervals
        .iter()
        .map(|&(start, end)| {
            (
                usize::try_from(start).expect("dense interval start must be non-negative"),
                usize::try_from(end).expect("dense interval end must be non-negative"),
            )
        })
        .collect()
}

fn to_dense_regions(interval_map: &IntervalMapND) -> Vec<DenseRegionND> {
    interval_map
        .iter()
        .map(|(spatial_start, intervals)| DenseRegionND {
            spatial_start: spatial_start.clone(),
            intervals: to_usize_intervals(intervals),
        })
        .collect()
}

fn retain_min_length(intervals: &mut Vec<(i64, i64)>, window_size: i64) {
    intervals.retain(|(start, end)| *end - *start >= window_size);
}

fn intersect_interval_maps(sources: &[&IntervalMapND], window_size: i64) -> IntervalMapND {
    if sources.is_empty() {
        return BTreeMap::new();
    }

    let common_keys: HashSet<Vec<usize>> =
        sources[1..]
            .iter()
            .fold(sources[0].keys().cloned().collect(), |acc: HashSet<Vec<usize>>, source| {
                let keys: HashSet<Vec<usize>> = source.keys().cloned().collect();
                acc.intersection(&keys).cloned().collect()
            });

    let mut sorted_keys: Vec<Vec<usize>> = common_keys.into_iter().collect();
    sorted_keys.sort();

    let mut result = BTreeMap::new();
    for key in sorted_keys {
        let interval_lists: Vec<Vec<(i64, i64)>> = sources
            .iter()
            .map(|source| source.get(&key).cloned().unwrap_or_default())
            .collect();
        let mut merged = intersect_interval_lists(&interval_lists);
        retain_min_length(&mut merged, window_size);
        if !merged.is_empty() {
            result.insert(key, merged);
        }
    }

    result
}

fn for_each_product(
    ranges: &[std::ops::RangeInclusive<usize>],
    callback: &mut impl FnMut(&[usize]),
) {
    fn rec(
        ranges: &[std::ops::RangeInclusive<usize>],
        current: &mut Vec<usize>,
        callback: &mut impl FnMut(&[usize]),
    ) {
        if current.len() == ranges.len() {
            callback(current);
            return;
        }
        let idx = current.len();
        for value in ranges[idx].clone() {
            current.push(value);
            rec(ranges, current, callback);
            current.pop();
        }
    }

    let mut current = Vec::with_capacity(ranges.len());
    rec(ranges, &mut current, callback);
}

// ---------------------------------------------------------------------------
// Temporal multiset per spatial window
// ---------------------------------------------------------------------------

fn build_spatial_t_events_with_predicate_nd(
    txns: &[TxnND],
    params: &MdNDParams,
    dims: &[usize],
    mut predicate: impl FnMut(&TxnND) -> bool,
) -> BTreeMap<Vec<usize>, Vec<i64>> {
    let spatial_window_bins = &params.window_bins[1..];
    let spatial_dims = &dims[1..];
    let mut map: BTreeMap<Vec<usize>, Vec<i64>> = BTreeMap::new();

    for tx in txns {
        if !predicate(tx) {
            continue;
        }

        let time = tx.coords[0] as i64;
        let ranges: Vec<std::ops::RangeInclusive<usize>> = tx.coords[1..]
            .iter()
            .zip(spatial_window_bins.iter())
            .zip(spatial_dims.iter())
            .map(|((&coord, &window), &dim_size)| {
                let start_lo = coord.saturating_sub(window - 1);
                let start_hi = coord.min(dim_size.saturating_sub(1));
                start_lo..=start_hi
            })
            .collect();

        for_each_product(&ranges, &mut |spatial_start| {
            map.entry(spatial_start.to_vec()).or_default().push(time);
        });
    }

    for times in map.values_mut() {
        times.sort_unstable();
    }
    map
}

fn build_spatial_t_events_for_item_nd(
    txns: &[TxnND],
    item: i64,
    params: &MdNDParams,
    dims: &[usize],
) -> BTreeMap<Vec<usize>, Vec<i64>> {
    build_spatial_t_events_with_predicate_nd(txns, params, dims, |tx| tx.items.contains(&item))
}

fn build_spatial_t_events_for_pattern_nd(
    txns: &[TxnND],
    pattern: &[i64],
    params: &MdNDParams,
    dims: &[usize],
) -> BTreeMap<Vec<usize>, Vec<i64>> {
    build_spatial_t_events_with_predicate_nd(txns, params, dims, |tx| {
        pattern.iter().all(|item| tx.items.contains(item))
    })
}

fn build_spatial_t_events_for_pattern_restricted_nd(
    txns: &[TxnND],
    pattern: &[i64],
    params: &MdNDParams,
    dims: &[usize],
    allowed_spatial_starts: &HashSet<Vec<usize>>,
) -> BTreeMap<Vec<usize>, Vec<i64>> {
    let spatial_window_bins = &params.window_bins[1..];
    let spatial_dims = &dims[1..];
    let mut map: BTreeMap<Vec<usize>, Vec<i64>> = BTreeMap::new();

    for tx in txns {
        if !pattern.iter().all(|item| tx.items.contains(item)) {
            continue;
        }

        let time = tx.coords[0] as i64;
        let ranges: Vec<std::ops::RangeInclusive<usize>> = tx.coords[1..]
            .iter()
            .zip(spatial_window_bins.iter())
            .zip(spatial_dims.iter())
            .map(|((&coord, &window), &dim_size)| {
                let start_lo = coord.saturating_sub(window - 1);
                let start_hi = coord.min(dim_size.saturating_sub(1));
                start_lo..=start_hi
            })
            .collect();

        for_each_product(&ranges, &mut |spatial_start| {
            if allowed_spatial_starts.contains(spatial_start) {
                map.entry(spatial_start.to_vec()).or_default().push(time);
            }
        });
    }

    for times in map.values_mut() {
        times.sort_unstable();
    }
    map
}

// ---------------------------------------------------------------------------
// t-axis interval computation
// ---------------------------------------------------------------------------

fn collapse_dense_lefts(
    _timestamps: &[i64],
    window_size: i64,
    dense_lefts: &[i64],
) -> Vec<(i64, i64)> {
    if dense_lefts.is_empty() {
        return Vec::new();
    }

    let mut intervals = Vec::new();
    let mut block_start = dense_lefts[0];
    let mut block_end = dense_lefts[0];

    for &left in dense_lefts.iter().skip(1) {
        if left == block_end + 1 {
            block_end = left;
            continue;
        }

        intervals.push((block_start, block_end + window_size));
        block_start = left;
        block_end = left;
    }

    intervals.push((block_start, block_end + window_size));
    intervals
}

fn compute_dense_intervals_multiset_naive(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
) -> Vec<(i64, i64)> {
    if timestamps.is_empty() || window_size < 1 || threshold < 1 {
        return Vec::new();
    }

    let ts_last = *timestamps.last().expect("timestamps should not be empty");
    let mut dense_lefts = Vec::new();
    for left in 0..=ts_last {
        let start_idx = lower_bound(timestamps, left);
        let end_idx = upper_bound(timestamps, left + window_size);
        if end_idx - start_idx >= threshold {
            dense_lefts.push(left);
        }
    }

    collapse_dense_lefts(timestamps, window_size, &dense_lefts)
}

fn compute_interval_map_nd(
    spatial_t_events: &BTreeMap<Vec<usize>, Vec<i64>>,
    params: &MdNDParams,
    data_length: i64,
) -> IntervalMapND {
    let window_size = effective_window_size(params.window_bins[0]);
    let mut interval_map = BTreeMap::new();

    for (spatial_start, timestamps) in spatial_t_events {
        let intervals = if params.use_t_stride {
            compute_dense_intervals_multiset(timestamps, window_size, params.threshold, data_length)
        } else {
            compute_dense_intervals_multiset_naive(timestamps, window_size, params.threshold)
        };
        if !intervals.is_empty() {
            interval_map.insert(spatial_start.clone(), intervals);
        }
    }

    interval_map
}

fn compute_interval_map_with_candidates_nd(
    spatial_t_events: &BTreeMap<Vec<usize>, Vec<i64>>,
    params: &MdNDParams,
    candidate_interval_map: &IntervalMapND,
    data_length: i64,
) -> IntervalMapND {
    let window_size = effective_window_size(params.window_bins[0]);
    let mut interval_map = BTreeMap::new();

    for (spatial_start, candidate_ranges) in candidate_interval_map {
        let Some(timestamps) = spatial_t_events.get(spatial_start) else {
            continue;
        };
        let intervals = compute_dense_intervals_with_candidates_multiset(
            timestamps,
            window_size,
            params.threshold,
            candidate_ranges,
            data_length,
        );
        if !intervals.is_empty() {
            interval_map.insert(spatial_start.clone(), intervals);
        }
    }

    interval_map
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

pub fn find_dense_itemsets_3d(
    transactions: &[(f64, f64, f64, Vec<i64>)],
    params: &Md3DParams,
) -> HashMap<Vec<i64>, Vec<DenseRegion>> {
    let raw_nd: Vec<(Vec<f64>, Vec<i64>)> = transactions
        .iter()
        .map(|(t, x, y, items)| (vec![*t, *x, *y], items.clone()))
        .collect();
    let params_nd = MdNDParams {
        bin_sizes: vec![params.bin_sizes.0, params.bin_sizes.1, params.bin_sizes.2],
        window_bins: vec![params.window_bins.0, params.window_bins.1, params.window_bins.2],
        threshold: params.threshold,
        max_length: params.max_length,
        ..Default::default()
    };
    find_dense_itemsets_nd(&raw_nd, &params_nd)
}

pub fn find_dense_itemsets_nd(
    raw: &[(Vec<f64>, Vec<i64>)],
    params: &MdNDParams,
) -> HashMap<Vec<i64>, Vec<DenseRegionND>> {
    let _ = (params.use_prefix_sum, params.use_binsearch);
    let (txns, dims) = discretize_nd(raw, params);
    if txns.is_empty() {
        return HashMap::new();
    }

    let mut all_items: Vec<i64> = txns
        .iter()
        .flat_map(|tx| tx.items.iter().copied())
        .collect();
    all_items.sort_unstable();
    all_items.dedup();

    let data_length = dims[0] as i64;
    let mut interval_maps: HashMap<Vec<i64>, IntervalMapND> = HashMap::new();
    let mut result: HashMap<Vec<i64>, Vec<DenseRegionND>> = HashMap::new();
    let mut current_level = Vec::new();

    for item in all_items {
        let spatial_t_events = build_spatial_t_events_for_item_nd(&txns, item, params, &dims);
        let interval_map = compute_interval_map_nd(&spatial_t_events, params, data_length);
        if interval_map.is_empty() {
            continue;
        }

        let key = vec![item];
        interval_maps.insert(key.clone(), interval_map.clone());
        result.insert(key.clone(), to_dense_regions(&interval_map));
        current_level.push(key);
    }

    let mut k = 2;
    while !current_level.is_empty() && params.max_length.map_or(true, |limit| k <= limit) {
        let prev_set: HashSet<Vec<i64>> = current_level.iter().cloned().collect();
        let candidates = if params.use_apriori_prune {
            prune_candidates(generate_candidates(&current_level, k), &prev_set)
        } else {
            generate_candidates(&current_level, k)
        };

        let mut next_level = Vec::new();
        for pattern in candidates {
            let interval_map = if params.use_apriori_prune {
                // Use (k-1)-subset interval maps for tighter pruning
                let subsets: Vec<Vec<i64>> = (0..pattern.len())
                    .map(|i| {
                        pattern.iter().enumerate()
                            .filter(|&(j, _)| j != i)
                            .map(|(_, &v)| v)
                            .collect()
                    })
                    .collect();

                let allowed_sources: Option<Vec<&IntervalMapND>> = subsets
                    .iter()
                    .map(|subset| interval_maps.get(subset))
                    .collect();
                let Some(allowed_sources) = allowed_sources else {
                    continue;
                };

                let candidate_interval_map = intersect_interval_maps(
                    &allowed_sources,
                    effective_window_size(params.window_bins[0]),
                );
                if candidate_interval_map.is_empty() {
                    continue;
                }

                // Only distribute to spatial starts that appear in C(P)
                let allowed_spatial_starts: HashSet<Vec<usize>> =
                    candidate_interval_map.keys().cloned().collect();
                let spatial_t_events = build_spatial_t_events_for_pattern_restricted_nd(
                    &txns, &pattern, params, &dims, &allowed_spatial_starts,
                );
                if spatial_t_events.is_empty() {
                    continue;
                }

                compute_interval_map_with_candidates_nd(
                    &spatial_t_events,
                    params,
                    &candidate_interval_map,
                    data_length,
                )
            } else {
                let spatial_t_events = build_spatial_t_events_for_pattern_nd(&txns, &pattern, params, &dims);
                if spatial_t_events.is_empty() {
                    continue;
                }
                compute_interval_map_nd(&spatial_t_events, params, data_length)
            };

            if interval_map.is_empty() {
                continue;
            }

            interval_maps.insert(pattern.clone(), interval_map.clone());
            result.insert(pattern.clone(), to_dense_regions(&interval_map));
            next_level.push(pattern);
        }

        current_level = next_level;
        k += 1;
    }

    result
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_txn(t: f64, x: f64, y: f64, items: Vec<i64>) -> (f64, f64, f64, Vec<i64>) {
        (t, x, y, items)
    }

    fn make_txn_nd(t: f64, x: f64, y: f64, items: Vec<i64>) -> (Vec<f64>, Vec<i64>) {
        (vec![t, x, y], items)
    }

    fn normalize_result(
        result: &HashMap<Vec<i64>, Vec<DenseRegionND>>,
    ) -> BTreeMap<Vec<i64>, BTreeMap<Vec<usize>, Vec<(usize, usize)>>> {
        let mut normalized = BTreeMap::new();
        let mut patterns: Vec<Vec<i64>> = result.keys().cloned().collect();
        patterns.sort();
        for pattern in patterns {
            let stripes = result.get(&pattern).unwrap();
            let mut by_spatial = BTreeMap::new();
            for stripe in stripes {
                by_spatial.insert(stripe.spatial_start.clone(), stripe.intervals.clone());
            }
            normalized.insert(pattern, by_spatial);
        }
        normalized
    }

    fn brute_interval_map_for_pattern(
        raw: &[(Vec<f64>, Vec<i64>)],
        pattern: &[i64],
        params: &MdNDParams,
    ) -> BTreeMap<Vec<usize>, Vec<(usize, usize)>> {
        let (txns, dims) = discretize_nd(raw, params);
        let spatial_t_events = build_spatial_t_events_for_pattern_nd(&txns, pattern, params, &dims);
        let window_size = effective_window_size(params.window_bins[0]);

        spatial_t_events
            .into_iter()
            .filter_map(|(spatial_start, timestamps)| {
                let intervals =
                    compute_dense_intervals_multiset_naive(&timestamps, window_size, params.threshold);
                if intervals.is_empty() {
                    None
                } else {
                    Some((spatial_start, to_usize_intervals(&intervals)))
                }
            })
            .collect()
    }

    fn brute_find_dense_itemsets_nd(
        raw: &[(Vec<f64>, Vec<i64>)],
        params: &MdNDParams,
    ) -> BTreeMap<Vec<i64>, BTreeMap<Vec<usize>, Vec<(usize, usize)>>> {
        let (txns, _) = discretize_nd(raw, params);
        if txns.is_empty() {
            return BTreeMap::new();
        }

        let mut all_items: Vec<i64> = txns
            .iter()
            .flat_map(|tx| tx.items.iter().copied())
            .collect();
        all_items.sort_unstable();
        all_items.dedup();

        let mut result = BTreeMap::new();
        let max_k = params.max_length.unwrap_or(all_items.len()).min(all_items.len());
        for k in 1..=max_k {
            for mut pattern in all_items.iter().copied().combinations(k) {
                pattern.sort_unstable();
                let interval_map = brute_interval_map_for_pattern(raw, &pattern, params);
                if !interval_map.is_empty() {
                    result.insert(pattern, interval_map);
                }
            }
        }
        result
    }

    #[test]
    fn test_planted_pair_is_detected_in_3d_interval_output() {
        let params = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (2, 2, 2),
            threshold: 3,
            max_length: Some(2),
        };

        let raw = vec![
            make_txn(0.0, 0.0, 0.0, vec![1, 2]),
            make_txn(0.0, 1.0, 0.0, vec![1, 2]),
            make_txn(1.0, 0.0, 1.0, vec![1, 2]),
            make_txn(1.0, 1.0, 1.0, vec![1, 2]),
            make_txn(4.0, 4.0, 4.0, vec![1]),
        ];

        let result = find_dense_itemsets_3d(&raw, &params);
        assert!(result.contains_key(&vec![1]));
        assert!(result.contains_key(&vec![2]));
        assert!(result.contains_key(&vec![1, 2]));
    }

    #[test]
    fn test_nd_matches_naive_interval_definition_on_small_case() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![2, 2, 2],
            threshold: 2,
            max_length: Some(2),
            ..Default::default()
        };

        let raw = vec![
            make_txn_nd(0.0, 0.0, 0.0, vec![1, 2]),
            make_txn_nd(0.0, 1.0, 0.0, vec![1]),
            make_txn_nd(1.0, 0.0, 1.0, vec![1, 2]),
            make_txn_nd(1.0, 1.0, 1.0, vec![2]),
            make_txn_nd(2.0, 1.0, 0.0, vec![1, 2]),
            make_txn_nd(3.0, 2.0, 1.0, vec![1]),
        ];

        let got = normalize_result(&find_dense_itemsets_nd(&raw, &params));
        let expected = brute_find_dense_itemsets_nd(&raw, &params);
        assert_eq!(got, expected);
    }

    #[test]
    fn test_nd_equals_3d() {
        let params_3d = Md3DParams {
            bin_sizes: (1.0, 1.0, 1.0),
            window_bins: (2, 2, 2),
            threshold: 2,
            max_length: Some(2),
        };
        let params_nd = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![2, 2, 2],
            threshold: 2,
            max_length: Some(2),
            ..Default::default()
        };

        let raw_3d = vec![
            make_txn(0.0, 0.0, 0.0, vec![1, 2]),
            make_txn(0.0, 1.0, 0.0, vec![1]),
            make_txn(1.0, 0.0, 1.0, vec![1, 2]),
            make_txn(1.0, 1.0, 1.0, vec![2]),
            make_txn(2.0, 1.0, 0.0, vec![1, 2]),
            make_txn(3.0, 2.0, 1.0, vec![1]),
        ];
        let raw_nd: Vec<(Vec<f64>, Vec<i64>)> = raw_3d
            .iter()
            .map(|(t, x, y, items)| (vec![*t, *x, *y], items.clone()))
            .collect();

        let got_3d = normalize_result(&find_dense_itemsets_3d(&raw_3d, &params_3d));
        let got_nd = normalize_result(&find_dense_itemsets_nd(&raw_nd, &params_nd));
        assert_eq!(got_3d, got_nd);
    }

    #[test]
    fn test_nd_without_t_stride_matches_default() {
        let raw = vec![
            make_txn_nd(0.0, 0.0, 0.0, vec![1, 2]),
            make_txn_nd(0.0, 1.0, 0.0, vec![1]),
            make_txn_nd(1.0, 0.0, 1.0, vec![1, 2]),
            make_txn_nd(1.0, 1.0, 1.0, vec![2]),
            make_txn_nd(2.0, 1.0, 0.0, vec![1, 2]),
            make_txn_nd(3.0, 2.0, 1.0, vec![1]),
        ];
        let params_stride = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![2, 2, 2],
            threshold: 2,
            max_length: Some(2),
            use_t_stride: true,
            ..Default::default()
        };
        let mut params_naive = params_stride.clone();
        params_naive.use_t_stride = false;

        let got_stride = normalize_result(&find_dense_itemsets_nd(&raw, &params_stride));
        let got_naive = normalize_result(&find_dense_itemsets_nd(&raw, &params_naive));
        assert_eq!(got_stride, got_naive);
    }

    #[test]
    fn test_nd_empty_transactions() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![2, 2, 2],
            threshold: 2,
            max_length: Some(2),
            ..Default::default()
        };
        let result = find_dense_itemsets_nd(&[], &params);
        assert!(result.is_empty());
    }

    #[test]
    fn test_nd_below_threshold_not_detected() {
        let params = MdNDParams {
            bin_sizes: vec![1.0, 1.0, 1.0],
            window_bins: vec![2, 1, 1],
            threshold: 4,
            max_length: Some(1),
            ..Default::default()
        };
        let raw = vec![
            make_txn_nd(0.0, 0.0, 0.0, vec![1]),
            make_txn_nd(1.0, 0.0, 0.0, vec![1]),
            make_txn_nd(1.0, 0.0, 1.0, vec![1]),
        ];
        let result = find_dense_itemsets_nd(&raw, &params);
        assert!(result.is_empty());
    }
}
