//! Ablation study for Apriori-Window 1D speedup techniques.
//!
//! Compares four algorithm variants on the same dataset:
//!   Naive          — no stride skipping, no Apriori pruning
//!   Stride-only    — stride skipping enabled, no Apriori pruning
//!   Pruning-only   — no stride skipping, Apriori pruning enabled
//!   Full           — stride skipping + Apriori pruning (proposed)
//!
//! Usage:
//!   # Real data
//!   cargo run --release --bin ablation -- <input.txt> <W> <threshold> <max_length>
//!
//!   # Synthetic data (T transactions, N items, W window, theta threshold, k max_length)
//!   cargo run --release --bin ablation -- --synth <T> <N> <W> <threshold> <max_length> [seed]

use std::env;
use std::path::PathBuf;
use std::time::Instant;

use apriori_window_1d::{
    find_dense_itemsets, find_dense_itemsets_naive, find_dense_itemsets_pruning_only,
    find_dense_itemsets_stride_only, read_text_file_as_2d_vec_of_integers,
};

/// Simple LCG pseudo-random number generator (no external dependency needed).
struct Lcg {
    state: u64,
}

impl Lcg {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.state
    }

    fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// Generate synthetic transaction stream.
///
/// Each item fires densely (prob=`dense_prob`) only in its own epoch of length
/// `epoch_len`, and sparsely (prob=`sparse_prob`) outside it. Epochs overlap by
/// `overlap` items so that k-subset candidates still exist but Apriori pruning
/// can eliminate the majority of the search space.
fn generate_synthetic(
    t_len: usize,
    n_items: usize,
    epoch_len: usize,
    dense_prob: f64,
    sparse_prob: f64,
    overlap: usize,
    seed: u64,
) -> Vec<Vec<i64>> {
    let mut rng = Lcg::new(seed);
    let mut transactions = Vec::with_capacity(t_len);

    // Each item i is dense in epoch [epoch_start(i), epoch_start(i) + epoch_len)
    let step = epoch_len.saturating_sub(overlap).max(1);
    let epoch_starts: Vec<usize> = (0..n_items).map(|i| (i * step) % t_len).collect();

    for t in 0..t_len {
        let tx: Vec<i64> = (0..n_items as i64)
            .filter(|&item| {
                let start = epoch_starts[item as usize];
                let end = (start + epoch_len) % t_len;
                let in_epoch = if start <= end {
                    t >= start && t < end
                } else {
                    t >= start || t < end
                };
                let prob = if in_epoch { dense_prob } else { sparse_prob };
                rng.next_f64() < prob
            })
            .collect();
        transactions.push(tx);
    }
    transactions
}

fn run_variants(
    transactions: &[Vec<i64>],
    window_size: i64,
    threshold: usize,
    max_length: usize,
) {
    type Fn = fn(&[Vec<i64>], i64, usize, usize) -> std::collections::HashMap<Vec<i64>, Vec<(i64, i64)>>;
    let variants: &[(&str, Fn)] = &[
        ("Naive", find_dense_itemsets_naive),
        ("Stride-only", find_dense_itemsets_stride_only),
        ("Pruning-only", find_dense_itemsets_pruning_only),
        ("Full (proposed)", find_dense_itemsets),
    ];

    println!("{:<18}  {:>10}  {:>10}", "Variant", "Time (ms)", "Patterns");
    println!("{}", "-".repeat(44));

    for (name, func) in variants {
        let t = Instant::now();
        let result = func(transactions, window_size, threshold, max_length);
        let elapsed_ms = t.elapsed().as_secs_f64() * 1000.0;
        let num_patterns: usize = result.values().map(|v| v.len()).sum();
        println!("{:<18}  {:>10.1}  {:>10}", name, elapsed_ms, num_patterns);
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() > 1 && args[1] == "--synth" {
        // Synthetic mode: --synth <T> <N> <W> <threshold> <max_length> [seed]
        if args.len() < 7 {
            eprintln!("Usage: ablation --synth <T> <N> <W> <threshold> <max_length> [seed]");
            std::process::exit(1);
        }
        let t_len: usize = args[2].parse().expect("T must be integer");
        let n_items: usize = args[3].parse().expect("N must be integer");
        let window_size: i64 = args[4].parse().expect("W must be integer");
        let threshold: usize = args[5].parse().expect("threshold must be integer");
        let max_length: usize = args[6].parse().expect("max_length must be integer");
        let seed: u64 = args.get(7).and_then(|s| s.parse().ok()).unwrap_or(42);

        // Each item has its own dense epoch; epochs overlap by 2 items to allow k-subsets
        let epoch_len = t_len / n_items * 3; // ~3x step so adjacent items share ~1/3 overlap
        let transactions =
            generate_synthetic(t_len, n_items, epoch_len, 0.8, 0.05, 2, seed);

        println!("Dataset : synthetic");
        println!(
            "T={t_len}, N={n_items}, W={window_size}, theta={threshold}, max_len={max_length}, seed={seed}"
        );
        println!();
        run_variants(&transactions, window_size, threshold, max_length);
    } else {
        // File mode: <input.txt> <W> <threshold> <max_length>
        if args.len() < 5 {
            eprintln!("Usage: ablation <input.txt> <W> <threshold> <max_length>");
            std::process::exit(1);
        }
        let input_path = PathBuf::from(&args[1]);
        let window_size: i64 = args[2].parse().expect("W must be integer");
        let threshold: usize = args[3].parse().expect("threshold must be integer");
        let max_length: usize = args[4].parse().expect("max_length must be integer");

        let transactions = read_text_file_as_2d_vec_of_integers(input_path.to_str().unwrap());
        let total = transactions.len();
        println!("Dataset : {}", input_path.display());
        println!("T={total}, W={window_size}, theta={threshold}, max_len={max_length}");
        println!();
        run_variants(&transactions, window_size, threshold, max_length);
    }
}
