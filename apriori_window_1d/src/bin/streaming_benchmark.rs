//! h-Step Streaming benchmark for Apriori-Window 1D.
//!
//! Usage (file):
//!   cargo run --release --bin streaming_benchmark -- <input.txt> <W> <threshold> <max_length>
//!
//! Usage (synthetic, EX-1):
//!   cargo run --release --bin streaming_benchmark -- --synth <T> <N> <W> <theta>

use std::env;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use apriori_window_1d::{find_dense_itemsets, read_text_file_as_2d_vec_of_integers};

// ── synthetic data generation ────────────────────────────────────────────────

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

// ── core streaming step ──────────────────────────────────────────────────────

/// Run h-step streaming over all transactions and return (elapsed, num_chunks).
fn run_hstep(
    transactions: &[Vec<i64>],
    window_size: i64,
    threshold: usize,
    max_length: usize,
    h: usize,
) -> (Duration, usize) {
    let total = transactions.len();
    let overlap = (window_size as usize).saturating_sub(1);
    let t_start = Instant::now();
    let mut num_chunks = 0usize;
    let mut pos = 0usize;
    while pos < total {
        let chunk_end = (pos + h).min(total);
        let buf_start = pos.saturating_sub(overlap);
        let buffer = &transactions[buf_start..chunk_end];
        let _ = find_dense_itemsets(buffer, window_size, threshold, max_length);
        pos = chunk_end;
        num_chunks += 1;
    }
    (t_start.elapsed(), num_chunks)
}

// ── main ─────────────────────────────────────────────────────────────────────

fn main() {
    let args: Vec<String> = env::args().collect();

    // ── EX-1 synthetic mode ──────────────────────────────────────────────────
    if args.len() > 1 && args[1] == "--synth" {
        if args.len() < 6 {
            eprintln!("Usage: streaming_benchmark --synth <T> <N> <W> <theta>");
            std::process::exit(1);
        }
        let t_len: usize = args[2].parse().expect("T");
        let n_items: usize = args[3].parse().expect("N");
        let window_size: i64 = args[4].parse().expect("W");
        let threshold: usize = args[5].parse().expect("theta");

        let transactions = generate_synthetic(t_len, n_items, 0.8, 0.05, 2, 42);
        let total = transactions.len();

        println!(
            "Dataset : synthetic  T={t_len}, N={n_items}, W={window_size}, theta={threshold}"
        );
        println!();

        let hs: Vec<usize> = vec![1, 10, 100, 1_000, total];

        println!("{:>10}  {:>12}  {:>10}", "h", "time_ms", "speedup");
        println!("{}", "-".repeat(36));

        let mut base_ms: Option<f64> = None;
        for &h in &hs {
            let (elapsed, _) =
                run_hstep(&transactions, window_size, threshold, usize::MAX, h);
            let ms = elapsed.as_secs_f64() * 1000.0;
            if base_ms.is_none() {
                base_ms = Some(ms);
            }
            let speedup = base_ms.unwrap() / ms;
            let label = if h == total {
                format!("{h} (batch)")
            } else {
                format!("{h}")
            };
            println!("{:>10}  {:>12.1}  {:>9.2}x", label, ms, speedup);
        }
        return;
    }

    // ── file mode (legacy) ───────────────────────────────────────────────────
    if args.len() < 5 {
        eprintln!(
            "Usage: streaming_benchmark <input.txt> <W> <threshold> <max_length>\n       \
             streaming_benchmark --synth <T> <N> <W> <theta>"
        );
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

    let mut hs: Vec<usize> = vec![1, 3, 6, 12, 24, 48, 96, 192, 512];
    hs.push(total);
    hs.retain(|&x| x <= total);
    hs.dedup();

    println!(
        "{:>8}  {:>12}  {:>12}  {:>8}  {:>14}",
        "h", "latency(tx)", "time_ms", "chunks", "throughput(tx/s)"
    );
    println!("{}", "-".repeat(62));

    for &h in &hs {
        let (elapsed, num_chunks) =
            run_hstep(&transactions, window_size, threshold, max_length, h);
        let time_ms = elapsed.as_secs_f64() * 1000.0;
        let throughput = total as f64 / elapsed.as_secs_f64();
        let label = if h == total {
            format!("{h} (batch)")
        } else {
            format!("{h}")
        };
        println!(
            "{:>8}  {:>12}  {:>12.1}  {:>8}  {:>14.0}",
            label, h, time_ms, num_chunks, throughput
        );
    }
}
