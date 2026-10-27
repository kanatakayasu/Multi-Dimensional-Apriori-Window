use crate::util::{lower_bound, upper_bound};

// ---------------------------------------------------------------------------
// Interval management helpers
// ---------------------------------------------------------------------------

pub fn find_covering_interval(intervals: &[(i64, i64)], point: i64) -> Option<(i64, i64)> {
    for (s, e) in intervals.iter().cloned() {
        if point >= s && point <= e {
            return Some((s, e));
        }
    }
    None
}

pub fn is_interval_covered(intervals: &[(i64, i64)], start: i64, end: i64) -> bool {
    intervals.iter().any(|(s, e)| start >= *s && end <= *e)
}

pub fn insert_and_merge_interval(intervals: &mut Vec<(i64, i64)>, new_interval: (i64, i64)) {
    intervals.push(new_interval);
    intervals.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    let mut merged: Vec<(i64, i64)> = Vec::new();
    for (s, e) in intervals.iter().cloned() {
        if let Some((last_s, last_e)) = merged.last_mut() {
            if s <= *last_e + 1 {
                *last_e = (*last_e).max(e);
                *last_s = (*last_s).min(s);
            } else {
                merged.push((s, e));
            }
        } else {
            merged.push((s, e));
        }
    }
    *intervals = merged;
}

// ---------------------------------------------------------------------------
// Dense interval computation
// ---------------------------------------------------------------------------

fn collapse_dense_lefts(window_size: i64, dense_lefts: &[i64]) -> Vec<(i64, i64)> {
    if dense_lefts.is_empty() {
        return Vec::new();
    }
    let mut intervals = Vec::new();
    let mut block_start = dense_lefts[0];
    let mut block_end = dense_lefts[0];
    for &l in dense_lefts.iter().skip(1) {
        if l == block_end + 1 {
            block_end = l;
        } else {
            intervals.push((block_start, block_end + window_size));
            block_start = l;
            block_end = l;
        }
    }
    intervals.push((block_start, block_end + window_size));
    intervals
}

/// Naive l++ scan with no stride skipping. Used as the baseline in ablation studies.
pub fn compute_dense_intervals_naive(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
) -> Vec<(i64, i64)> {
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() {
        return Vec::new();
    }
    let ts = timestamps;
    let ts_last = *ts.last().unwrap();
    let mut dense_lefts = Vec::new();
    for l in 0..=ts_last {
        let start_idx = lower_bound(ts, l);
        let end_idx = upper_bound(ts, l + window_size);
        if end_idx - start_idx >= threshold {
            dense_lefts.push(l);
        }
    }
    collapse_dense_lefts(window_size, &dense_lefts)
}

/// Naive l++ scan restricted to candidate ranges. Used in Pruning-only variant.
pub fn compute_dense_intervals_naive_with_candidates(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
    candidate_ranges: &[(i64, i64)],
) -> Vec<(i64, i64)> {
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() || candidate_ranges.is_empty() {
        return Vec::new();
    }
    let ts = timestamps;
    let ts_last = *ts.last().unwrap();
    let mut dense_lefts = Vec::new();
    for &(raw_start, raw_end) in candidate_ranges {
        let start = raw_start.max(0);
        let end = raw_end.min(ts_last);
        if start > end {
            continue;
        }
        for l in start..=end {
            let start_idx = lower_bound(ts, l);
            let end_idx = upper_bound(ts, l + window_size);
            if end_idx - start_idx >= threshold {
                dense_lefts.push(l);
            }
        }
    }
    dense_lefts.sort_unstable();
    dense_lefts.dedup();
    collapse_dense_lefts(window_size, &dense_lefts)
}

fn earliest_dense_left(
    timestamps: &[i64],
    start_idx: usize,
    window_size: i64,
    threshold: usize,
    min_left: i64,
) -> Option<i64> {
    let anchor_idx = start_idx + threshold.checked_sub(1)?;
    if anchor_idx >= timestamps.len() {
        return None;
    }
    Some(min_left.max((timestamps[anchor_idx] - window_size).max(0)))
}

pub fn compute_dense_intervals(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
    _data_length: i64,
) -> Vec<(i64, i64)> {
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() {
        return Vec::new();
    }

    let ts = timestamps;
    let mut intervals: Vec<(i64, i64)> = Vec::new();
    let Some(mut l) = earliest_dense_left(ts, 0, window_size, threshold, 0) else {
        return Vec::new();
    };
    let mut in_dense = false;
    let mut start: Option<i64> = None;
    let mut interval_end: Option<i64> = None;
    let ts_last = *ts.last().expect("timestamps should not be empty");

    while l <= ts_last {
        let start_idx = lower_bound(ts, l);
        let end_idx = upper_bound(ts, l + window_size);
        let count = end_idx - start_idx;

        if count < threshold {
            if in_dense {
                if let (Some(s), Some(e)) = (start, interval_end) {
                    intervals.push((s, e));
                }
            }
            in_dense = false;
            start = None;
            interval_end = None;
            // Jump to the position where enough occurrences enter the window
            // to potentially reach threshold (deficit-aware stride).
            let deficit = threshold - count;
            let jump_idx = end_idx + deficit - 1;
            if jump_idx >= ts.len() {
                break;
            }
            let next_needed = ts[jump_idx];
            l = (l + 1).max(next_needed - window_size);
            continue;
        }

        // count >= threshold: dense window.
        if !in_dense {
            in_dense = true;
            start = Some(l);
        }

        let surplus = count - threshold;
        let last_dense_left = ts[start_idx + surplus];
        interval_end = Some(last_dense_left + window_size);
        l = last_dense_left + 1;
    }

    if in_dense {
        if let (Some(s), Some(e)) = (start, interval_end) {
            intervals.push((s, e));
        }
    }

    intervals
}

/// Duplicate-aware variant of `compute_dense_intervals`.
///
/// `timestamps` may contain repeated values. The algorithm emits the maximal
/// dense-left block guaranteed by the current window, then advances just past
/// that block. The output interval semantics stay identical to the unique-time
/// version: each returned pair is `(dense_block_start, rightmost_reachable_occurrence)`.
pub fn compute_dense_intervals_multiset(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
    _data_length: i64,
) -> Vec<(i64, i64)> {
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() {
        return Vec::new();
    }

    let ts = timestamps;
    let Some(mut l) = earliest_dense_left(ts, 0, window_size, threshold, 0) else {
        return Vec::new();
    };
    let mut intervals: Vec<(i64, i64)> = Vec::new();
    let mut in_dense = false;
    let mut start: Option<i64> = None;
    let mut interval_end: Option<i64> = None;
    let ts_last = *ts.last().expect("timestamps should not be empty");

    while l <= ts_last {
        let start_idx = lower_bound(ts, l);
        let end_idx = upper_bound(ts, l + window_size);
        let count = end_idx - start_idx;

        if count < threshold {
            if in_dense {
                if let (Some(s), Some(e)) = (start, interval_end) {
                    intervals.push((s, e));
                }
            }
            in_dense = false;
            start = None;
            interval_end = None;
            let deficit = threshold - count;
            let jump_idx = end_idx + deficit - 1;
            if jump_idx >= ts.len() {
                break;
            }
            let next_needed = ts[jump_idx];
            l = (l + 1).max(next_needed - window_size);
            continue;
        }

        let surplus = count - threshold;
        let dense_end = ts[start_idx + surplus];

        if !in_dense {
            in_dense = true;
            start = Some(l);
        }
        interval_end = Some(dense_end + window_size);

        l = dense_end + 1;
    }

    if in_dense {
        if let (Some(s), Some(e)) = (start, interval_end) {
            intervals.push((s, e));
        }
    }

    intervals
}

/// `candidate_ranges` are contiguous intervals of valid left endpoints `l`.
/// When a +1 stride would leave the current candidate range, we fold in the
/// boundary window at `c_end` before terminating that range.
pub fn compute_dense_intervals_with_candidates(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
    candidate_ranges: &[(i64, i64)],
    _data_length: i64,
) -> Vec<(i64, i64)> {
    if candidate_ranges.is_empty() {
        return Vec::new();
    }
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() {
        return Vec::new();
    }

    let ts = timestamps;
    let mut intervals: Vec<(i64, i64)> = Vec::new();
    let ts_last = *ts.last().expect("timestamps should not be empty");
    let mut recorded: Vec<(i64, i64)> = Vec::new();

    let mut sorted_candidates = candidate_ranges.to_vec();
    sorted_candidates.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    let mut merged_candidates: Vec<(i64, i64)> = Vec::new();
    for (start, end) in sorted_candidates {
        if let Some((_, last_end)) = merged_candidates.last_mut() {
            if start <= *last_end + 1 {
                *last_end = (*last_end).max(end);
                continue;
            }
        }
        merged_candidates.push((start, end));
    }

    for (raw_c_start, c_end) in merged_candidates {
        if c_end < 0 {
            continue;
        }
        let c_start = raw_c_start.max(0);
        if c_start > c_end {
            continue;
        }
        let first_idx = lower_bound(ts, c_start);
        let Some(mut l) = earliest_dense_left(ts, first_idx, window_size, threshold, c_start)
        else {
            break;
        };
        if l > c_end || l > ts_last {
            continue;
        }
        let mut in_dense = false;
        let mut start: Option<i64> = None;
        let mut interval_end: Option<i64> = None;
        let mut dense_end: Option<i64> = None;

        while l <= c_end && l <= ts_last {
            if let Some((_, rec_end)) = find_covering_interval(&recorded, l) {
                let next_l = rec_end + 1;
                if next_l > c_end {
                    break;
                }
                l = next_l;
                continue;
            }
            let start_idx = lower_bound(ts, l);
            let end_idx = upper_bound(ts, l + window_size);
            let count = end_idx - start_idx;

            if count < threshold {
                if in_dense {
                    if let (Some(s), Some(e), Some(d_end)) = (start, interval_end, dense_end) {
                        if !is_interval_covered(&recorded, s, d_end) {
                            intervals.push((s, e));
                            insert_and_merge_interval(&mut recorded, (s, d_end));
                        }
                    }
                }
                in_dense = false;
                start = None;
                interval_end = None;
                dense_end = None;
                let deficit = threshold - count;
                let jump_idx = end_idx + deficit - 1;
                if jump_idx >= ts.len() {
                    break;
                }
                let next_needed = ts[jump_idx];
                let next_l = (l + 1).max(next_needed - window_size);
                if next_l > c_end {
                    break;
                }
                l = next_l;
                continue;
            }

            // candidate_ranges are intervals of valid left endpoints.
            // When +1 stride would step past c_end, fold in the boundary
            // window [c_end, c_end + W] before exiting this candidate range.
            if !in_dense {
                in_dense = true;
                start = Some(l);
            }

            let surplus = count - threshold;
            let jump_to = ts[start_idx + surplus];
            let candidate_next_l = jump_to + 1;
            if candidate_next_l > c_end {
                let last_dense_left = jump_to.min(c_end);
                interval_end = Some(last_dense_left + window_size);
                dense_end = Some(last_dense_left);
                break;
            }
            interval_end = Some(jump_to + window_size);
            dense_end = Some(jump_to);
            l = candidate_next_l;
        }

        if in_dense {
            if let (Some(s), Some(e), Some(d_end)) = (start, interval_end, dense_end) {
                if !is_interval_covered(&recorded, s, d_end) {
                    intervals.push((s, e));
                    insert_and_merge_interval(&mut recorded, (s, d_end));
                }
            }
        }
    }

    intervals
}

/// Duplicate-aware variant of `compute_dense_intervals_with_candidates`.
///
/// `candidate_ranges` are intervals of valid left endpoints. For a dense window,
/// the current window guarantees a whole dense-left block `[l, dense_end]`; if
/// that block crosses `c_end`, the algorithm truncates it to `c_end` and folds
/// in the boundary window implicitly via `block_rightmost(c_end)`.
pub fn compute_dense_intervals_with_candidates_multiset(
    timestamps: &[i64],
    window_size: i64,
    threshold: usize,
    candidate_ranges: &[(i64, i64)],
    _data_length: i64,
) -> Vec<(i64, i64)> {
    if candidate_ranges.is_empty() {
        return Vec::new();
    }
    if window_size < 1 || threshold < 1 {
        panic!("window_size and threshold must be >= 1");
    }
    if timestamps.is_empty() {
        return Vec::new();
    }

    let ts = timestamps;
    let ts_last = *ts.last().expect("timestamps should not be empty");
    let mut intervals: Vec<(i64, i64)> = Vec::new();
    let mut recorded: Vec<(i64, i64)> = Vec::new();

    let mut sorted_candidates = candidate_ranges.to_vec();
    sorted_candidates.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    let mut merged_candidates: Vec<(i64, i64)> = Vec::new();
    for (start, end) in sorted_candidates {
        if let Some((_, last_end)) = merged_candidates.last_mut() {
            if start <= *last_end + 1 {
                *last_end = (*last_end).max(end);
                continue;
            }
        }
        merged_candidates.push((start, end));
    }

    for (raw_c_start, c_end) in merged_candidates {
        if c_end < 0 {
            continue;
        }
        let c_start = raw_c_start.max(0);
        if c_start > c_end {
            continue;
        }

        let first_idx = lower_bound(ts, c_start);
        let Some(mut l) = earliest_dense_left(ts, first_idx, window_size, threshold, c_start)
        else {
            break;
        };
        if l > c_end || l > ts_last {
            continue;
        }

        let mut in_dense = false;
        let mut start: Option<i64> = None;
        let mut interval_end: Option<i64> = None;
        let mut dense_end: Option<i64> = None;

        while l <= c_end && l <= ts_last {
            if let Some((_, rec_end)) = find_covering_interval(&recorded, l) {
                let next_l = rec_end + 1;
                if next_l > c_end {
                    break;
                }
                l = next_l;
                continue;
            }

            let start_idx = lower_bound(ts, l);
            let end_idx = upper_bound(ts, l + window_size);
            let count = end_idx - start_idx;

            if count < threshold {
                if in_dense {
                    if let (Some(s), Some(e), Some(d_end)) = (start, interval_end, dense_end) {
                        if !is_interval_covered(&recorded, s, d_end) {
                            intervals.push((s, e));
                            insert_and_merge_interval(&mut recorded, (s, d_end));
                        }
                    }
                }
                in_dense = false;
                start = None;
                interval_end = None;
                dense_end = None;
                let deficit = threshold - count;
                let jump_idx = end_idx + deficit - 1;
                if jump_idx >= ts.len() {
                    break;
                }
                let next_needed = ts[jump_idx];
                let next_l = (l + 1).max(next_needed - window_size);
                if next_l > c_end {
                    break;
                }
                l = next_l;
                continue;
            }

            let surplus = count - threshold;
            let dense_block_end = ts[start_idx + surplus].min(c_end);

            if !in_dense {
                in_dense = true;
                start = Some(l);
            }
            interval_end = Some(dense_block_end + window_size);
            dense_end = Some(dense_block_end);

            let next_l = dense_block_end + 1;
            if next_l > c_end {
                break;
            }
            l = next_l;
        }

        if in_dense {
            if let (Some(s), Some(e), Some(d_end)) = (start, interval_end, dense_end) {
                if !is_interval_covered(&recorded, s, d_end) {
                    intervals.push((s, e));
                    insert_and_merge_interval(&mut recorded, (s, d_end));
                }
            }
        }
    }

    intervals
}

#[cfg(test)]
mod tests {
    use super::{
        compute_dense_intervals, compute_dense_intervals_multiset,
        compute_dense_intervals_naive, compute_dense_intervals_with_candidates,
        compute_dense_intervals_with_candidates_multiset, upper_bound,
    };
    use crate::util::lower_bound;

    fn compute_dense_intervals_with_candidates_naive(
        timestamps: &[i64],
        window_size: i64,
        threshold: usize,
        candidate_ranges: &[(i64, i64)],
    ) -> Vec<(i64, i64)> {
        super::compute_dense_intervals_naive_with_candidates(
            timestamps,
            window_size,
            threshold,
            candidate_ranges,
        )
    }

    fn candidate_range_sets(max_coord: i64) -> Vec<Vec<(i64, i64)>> {
        let mut all_ranges = Vec::new();
        for start in 0..=max_coord {
            for end in start..=max_coord {
                all_ranges.push((start, end));
            }
        }

        let mut sets = vec![Vec::new()];
        for range in &all_ranges {
            sets.push(vec![*range]);
        }
        for i in 0..all_ranges.len() {
            for j in (i + 1)..all_ranges.len() {
                sets.push(vec![all_ranges[i], all_ranges[j]]);
            }
        }
        sets
    }

    fn combinations(
        values: &[i64],
        choose: usize,
        start: usize,
        current: &mut Vec<i64>,
        out: &mut Vec<Vec<i64>>,
    ) {
        if current.len() == choose {
            out.push(current.clone());
            return;
        }
        for idx in start..values.len() {
            current.push(values[idx]);
            combinations(values, choose, idx + 1, current, out);
            current.pop();
        }
    }

    fn unique_timestamp_sets(max_len: usize, max_value: i64) -> Vec<Vec<i64>> {
        let values: Vec<i64> = (0..max_value).collect();
        let mut sets = Vec::new();
        for choose in 1..=max_len {
            combinations(&values, choose, 0, &mut Vec::new(), &mut sets);
        }
        sets
    }

    fn nondecreasing_timestamp_sets(max_len: usize, max_value: i64) -> Vec<Vec<i64>> {
        fn rec(
            max_len: usize,
            max_value: i64,
            min_value: i64,
            current: &mut Vec<i64>,
            out: &mut Vec<Vec<i64>>,
        ) {
            if !current.is_empty() {
                out.push(current.clone());
            }
            if current.len() == max_len {
                return;
            }
            for value in min_value..max_value {
                current.push(value);
                rec(max_len, max_value, value, current, out);
                current.pop();
            }
        }

        let mut sets = Vec::new();
        rec(max_len, max_value, 0, &mut Vec::new(), &mut sets);
        sets
    }

    #[test]
    fn compute_dense_intervals_matches_naive_definition_on_small_inputs() {
        for ts in unique_timestamp_sets(5, 8) {
            for window_size in 1..=5 {
                for threshold in 1..=4 {
                    let new_intervals =
                        compute_dense_intervals(&ts, window_size, threshold, ts.len() as i64);
                    let naive_intervals =
                        compute_dense_intervals_naive(&ts, window_size, threshold);
                    assert_eq!(
                        new_intervals, naive_intervals,
                        "mismatch for ts={ts:?}, W={window_size}, theta={threshold}"
                    );
                }
            }
        }
    }

    #[test]
    fn compute_dense_intervals_starts_at_theta_th_occurrence_boundary() {
        let ts = [5, 8];
        let intervals = compute_dense_intervals(&ts, 5, 2, ts.len() as i64);
        // dense-left block is [3, 5], so interval = (3, 5+5) = (3, 10)
        assert_eq!(intervals, vec![(3, 10)]);
    }

    #[test]
    fn compute_dense_intervals_uses_next_outside_jump_for_count_below_threshold() {
        let ts = [0, 4, 10, 11, 12];
        let intervals = compute_dense_intervals(&ts, 6, 3, ts.len() as i64);
        // dense-left block is [6, 10], so interval = (6, 10+6) = (6, 16)
        assert_eq!(intervals, vec![(6, 16)]);
    }

    #[test]
    fn compute_dense_intervals_with_candidates_matches_naive_definition_on_small_inputs() {
        let candidate_sets = candidate_range_sets(4);
        for ts in unique_timestamp_sets(4, 7) {
            for window_size in 1..=4 {
                for threshold in 1..=3 {
                    for candidate_ranges in &candidate_sets {
                        let new_intervals = compute_dense_intervals_with_candidates(
                            &ts,
                            window_size,
                            threshold,
                            candidate_ranges,
                            ts.len() as i64,
                        );
                        let naive_intervals = compute_dense_intervals_with_candidates_naive(
                            &ts,
                            window_size,
                            threshold,
                            candidate_ranges,
                        );
                        assert_eq!(
                            new_intervals, naive_intervals,
                            "mismatch for ts={ts:?}, W={window_size}, theta={threshold}, cands={candidate_ranges:?}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn compute_dense_intervals_with_candidates_keeps_candidate_end_dense_window() {
        let ts = [1, 2];
        let intervals =
            compute_dense_intervals_with_candidates(&ts, 1, 1, &[(0, 1)], ts.len() as i64);
        assert_eq!(intervals, vec![(0, 2)]);
    }

    #[test]
    fn compute_dense_intervals_with_candidates_updates_rightmost_at_candidate_boundary() {
        let ts = [5, 8, 9, 11];
        let intervals =
            compute_dense_intervals_with_candidates(&ts, 4, 2, &[(5, 8)], ts.len() as i64);
        // dense-left block [5, 8], last_dense_left=8, interval = (5, 8+4) = (5, 12)
        assert_eq!(intervals, vec![(5, 12)]);
    }

    #[test]
    fn compute_dense_intervals_with_candidates_uses_c_end_when_stride_skips_past_it() {
        let ts = [0, 1, 3, 4];
        let intervals =
            compute_dense_intervals_with_candidates(&ts, 2, 1, &[(0, 2)], ts.len() as i64);
        assert_eq!(intervals, vec![(0, 4)]);
    }

    #[test]
    fn compute_dense_intervals_with_candidates_starts_before_first_event_when_needed() {
        let ts = [5, 8];
        let intervals =
            compute_dense_intervals_with_candidates(&ts, 5, 2, &[(0, 8)], ts.len() as i64);
        // dense-left block [3, 5], last_dense_left=5, interval = (3, 5+5) = (3, 10)
        assert_eq!(intervals, vec![(3, 10)]);
    }

    #[test]
    fn compute_dense_intervals_multiset_matches_naive_definition_on_small_inputs() {
        for ts in nondecreasing_timestamp_sets(5, 6) {
            for window_size in 1..=4 {
                for threshold in 1..=4 {
                    let got = compute_dense_intervals_multiset(
                        &ts,
                        window_size,
                        threshold,
                        ts.len() as i64,
                    );
                    let expected = compute_dense_intervals_naive(&ts, window_size, threshold);
                    assert_eq!(
                        got, expected,
                        "mismatch for multiset ts={ts:?}, W={window_size}, theta={threshold}"
                    );
                }
            }
        }
    }

    #[test]
    fn compute_dense_intervals_multiset_keeps_dense_block_with_duplicate_midpoint() {
        let ts = [0, 1, 1, 2];
        let intervals = compute_dense_intervals_multiset(&ts, 1, 2, ts.len() as i64);
        assert_eq!(intervals, vec![(0, 2)]);
    }

    #[test]
    fn compute_dense_intervals_with_candidates_multiset_matches_naive_definition() {
        let candidate_sets = candidate_range_sets(4);
        for ts in nondecreasing_timestamp_sets(4, 6) {
            for window_size in 1..=3 {
                for threshold in 1..=3 {
                    for candidate_ranges in &candidate_sets {
                        let got = compute_dense_intervals_with_candidates_multiset(
                            &ts,
                            window_size,
                            threshold,
                            candidate_ranges,
                            ts.len() as i64,
                        );
                        let expected = compute_dense_intervals_with_candidates_naive(
                            &ts,
                            window_size,
                            threshold,
                            candidate_ranges,
                        );
                        assert_eq!(
                            got, expected,
                            "mismatch for multiset ts={ts:?}, W={window_size}, theta={threshold}, cands={candidate_ranges:?}"
                        );
                    }
                }
            }
        }
    }
}
