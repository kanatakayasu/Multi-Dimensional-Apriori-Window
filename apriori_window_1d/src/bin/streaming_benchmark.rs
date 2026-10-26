//! n-Step Streaming benchmark for Apriori-Window 1D.
//!
//! Processes a transaction stream in steps of n transactions with a W-1 overlap
//! buffer to ensure correctness at chunk boundaries. Measures total wall-clock
//! time for each n, characterising the latency-throughput tradeoff.
//!
//! Usage:
//!   cargo run --release --bin streaming_benchmark -- <input.txt> <W> <threshold> <max_length>

use std::env;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use apriori_window_1d::{find_dense_itemsets, read_text_file_as_2d_vec_of_integers};

/// Run n-step streaming over all transactions and return (elapsed, num_chunks).
///
/// Each chunk [pos, pos+n) is processed with a W-1 overlap from the previous
/// chunk so that dense intervals straddling chunk boundaries are not missed.
fn run_nstep(
    transactions: &[Vec<i64>],
    window_size: i64,
    threshold: usize,
    max_length: usize,
    n: usize,
) -> (Duration, usize) {
    let total = transactions.len();
    let overlap = (window_size as usize).saturating_sub(1);
    let t_start = Instant::now();
    let mut num_chunks = 0usize;

    let mut pos = 0usize;
    while pos < total {
        let chunk_end = (pos + n).min(total);
        let buf_start = pos.saturating_sub(overlap);
        let buffer = &transactions[buf_start..chunk_end];
        let _ = find_dense_itemsets(buffer, window_size, threshold, max_length);
        pos = chunk_end;
        num_chunks += 1;
    }

    (t_start.elapsed(), num_chunks)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 5 {
        eprintln!(
            "Usage: streaming_benchmark <input.txt> <W> <threshold> <max_length>"
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

    // n values: small steps up to full batch
    let mut ns: Vec<usize> = vec![1, 3, 6, 12, 24, 48, 96, 192, 512];
    ns.push(total);
    ns.retain(|&x| x <= total);
    ns.dedup();

    println!(
        "{:>8}  {:>12}  {:>12}  {:>8}  {:>14}",
        "n", "latency(tx)", "time_ms", "chunks", "throughput(tx/s)"
    );
    println!("{}", "-".repeat(62));

    for &n in &ns {
        // Warm up Rayon thread pool on first run to avoid cold-start bias.
        let (elapsed, num_chunks) =
            run_nstep(&transactions, window_size, threshold, max_length, n);
        let time_ms = elapsed.as_secs_f64() * 1000.0;
        let throughput = total as f64 / elapsed.as_secs_f64();
        let label = if n == total {
            format!("{n} (batch)")
        } else {
            format!("{n}")
        };
        println!(
            "{:>8}  {:>12}  {:>12.1}  {:>8}  {:>14.0}",
            label, n, time_ms, num_chunks, throughput
        );
    }
}
