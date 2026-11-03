//! Single-point scalability benchmark for AROB EX-2.
//!
//! Generates a synthetic stream, runs the Full algorithm (h = T, i.e. batch),
//! and prints the elapsed time in milliseconds to stdout.
//!
//! Usage:
//!   scalability <T> <N> <W> <theta>
//!
//! Stdout: one line "<time_ms>" (suitable for /usr/bin/time -l wrapping).

use std::env;
use std::time::Instant;

use apriori_window_1d::find_dense_itemsets;

struct Lcg {
    state: u64,
}
impl Lcg {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }
    fn next_f64(&mut self) -> f64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.state >> 11) as f64 / (1u64 << 53) as f64
    }
}

fn generate_synthetic(
    t_len: usize,
    n_items: usize,
    dense_prob: f64,
    sparse_prob: f64,
    overlap: usize,
    seed: u64,
) -> Vec<Vec<i64>> {
    let mut rng = Lcg::new(seed);
    let epoch_len = (t_len / n_items * 3).max(1);
    let step = epoch_len.saturating_sub(overlap).max(1);
    let starts: Vec<usize> = (0..n_items).map(|i| (i * step) % t_len).collect();
    (0..t_len)
        .map(|t| {
            (0..n_items as i64)
                .filter(|&item| {
                    let s = starts[item as usize];
                    let e = (s + epoch_len) % t_len;
                    let in_e = if s <= e { t >= s && t < e } else { t >= s || t < e };
                    rng.next_f64() < if in_e { dense_prob } else { sparse_prob }
                })
                .collect()
        })
        .collect()
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 5 {
        eprintln!("Usage: scalability <T> <N> <W> <theta>");
        std::process::exit(1);
    }
    let t_len: usize = args[1].parse().expect("T");
    let n_items: usize = args[2].parse().expect("N");
    let window_size: i64 = args[3].parse().expect("W");
    let threshold: usize = args[4].parse().expect("theta");

    let transactions = generate_synthetic(t_len, n_items, 0.8, 0.05, 2, 42);

    let start = Instant::now();
    let _ = find_dense_itemsets(&transactions, window_size, threshold, usize::MAX);
    let ms = start.elapsed().as_secs_f64() * 1000.0;

    println!("{:.3}", ms);
}
