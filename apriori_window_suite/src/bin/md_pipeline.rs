//! 多次元 Apriori-Window CLI バイナリ
//!
//! USAGE:
//!   md_pipeline gen  --out PATH --n-txn N [OPTIONS]
//!   md_pipeline run  --input PATH [OPTIONS]
//!
//! GEN OPTIONS:
//!   --out PATH        出力ファイル（TSV: t x y items...）
//!   --n-txn N         トランザクション数（デフォルト 5000）
//!   --seed S          乱数シード（デフォルト 42）
//!   --n-items N       アイテム種類数（デフォルト 20）
//!   --dense-regions N 植え付け密集領域数（デフォルト 3）
//!
//! RUN OPTIONS:
//!   --input PATH      入力 TSV ファイル
//!   --dt F            t ビン幅（デフォルト 1.0）
//!   --dx F            x ビン幅（デフォルト 1.0）
//!   --dy F            y ビン幅（デフォルト 1.0）
//!   --wt N            t ウィンドウビン数（デフォルト 5）
//!   --wx N            x ウィンドウビン数（デフォルト 3）
//!   --wy N            y ウィンドウビン数（デフォルト 3）
//!   --threshold N     サポート閾値（デフォルト 3）
//!   --max-length N    最大パターン長（デフォルト 3）

use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::time::Instant;

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

use apriori_window_suite::md_apriori::{find_dense_itemsets_3d, Md3DParams};

// ---------------------------------------------------------------------------
// CLI パース（外部クレート不使用）
// ---------------------------------------------------------------------------

fn parse_args() -> HashMap<String, String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut map = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        if args[i].starts_with("--") {
            let key = args[i].trim_start_matches('-').to_string();
            if i + 1 < args.len() && !args[i + 1].starts_with("--") {
                map.insert(key, args[i + 1].clone());
                i += 2;
            } else {
                map.insert(key, "true".to_string());
                i += 1;
            }
        } else {
            map.insert("subcommand".to_string(), args[i].clone());
            i += 1;
        }
    }
    map
}

// ---------------------------------------------------------------------------
// 合成データ生成
// ---------------------------------------------------------------------------

fn cmd_gen(args: &HashMap<String, String>) {
    let out = args.get("out").map(|s| s.as_str()).unwrap_or("md_data.tsv");
    let n_txn: usize = args
        .get("n-txn")
        .and_then(|s| s.parse().ok())
        .unwrap_or(5000);
    let seed: u64 = args.get("seed").and_then(|s| s.parse().ok()).unwrap_or(42);
    let n_items: usize = args
        .get("n-items")
        .and_then(|s| s.parse().ok())
        .unwrap_or(20);
    let n_dense: usize = args
        .get("dense-regions")
        .and_then(|s| s.parse().ok())
        .unwrap_or(3);

    let mut rng = StdRng::seed_from_u64(seed);
    let t_max = 100.0_f64;
    let xy_max = 50.0_f64;

    // 密集領域の中心を決定
    let dense_centers: Vec<(f64, f64, f64, Vec<i64>)> = (0..n_dense)
        .map(|i| {
            let tc = rng.gen_range(10.0..t_max - 10.0);
            let xc = rng.gen_range(5.0..xy_max - 5.0);
            let yc = rng.gen_range(5.0..xy_max - 5.0);
            // 密集領域ごとに 2 つのアイテムを割り当て
            let item_a = (i * 2 + 1) as i64;
            let item_b = (i * 2 + 2) as i64;
            (tc, xc, yc, vec![item_a, item_b])
        })
        .collect();

    // 密集トランザクションを植え付け（各領域に 20 件）
    let mut records: Vec<(f64, f64, f64, Vec<i64>)> = Vec::new();
    for (tc, xc, yc, items) in &dense_centers {
        for _ in 0..20 {
            let t = tc + rng.gen_range(-2.0..2.0);
            let x = xc + rng.gen_range(-1.0..1.0);
            let y = yc + rng.gen_range(-1.0..1.0);
            records.push((t.max(0.0), x.max(0.0), y.max(0.0), items.clone()));
        }
    }

    // バックグラウンドノイズ
    for _ in 0..(n_txn - records.len()) {
        let t = rng.gen_range(0.0..t_max);
        let x = rng.gen_range(0.0..xy_max);
        let y = rng.gen_range(0.0..xy_max);
        let n = rng.gen_range(1..=4);
        let items: Vec<i64> = (0..n)
            .map(|_| rng.gen_range(1..=n_items as i64))
            .collect();
        records.push((t, x, y, items));
    }

    // 書き出し
    let mut f = fs::File::create(out).expect("出力ファイル作成失敗");
    writeln!(f, "# t\tx\ty\titems...").unwrap();
    for (t, x, y, items) in &records {
        let items_str: Vec<String> = items.iter().map(|i| i.to_string()).collect();
        writeln!(f, "{:.3}\t{:.3}\t{:.3}\t{}", t, x, y, items_str.join(",")).unwrap();
    }

    eprintln!("生成完了: {} 件 → {}", records.len(), out);
    eprintln!("植え付け密集領域:");
    for (i, (tc, xc, yc, items)) in dense_centers.iter().enumerate() {
        eprintln!(
            "  Region {}: t={:.1} x={:.1} y={:.1} items={:?}",
            i + 1,
            tc,
            xc,
            yc,
            items
        );
    }
}

// ---------------------------------------------------------------------------
// 入力ファイル読み込み
// ---------------------------------------------------------------------------

fn read_tsv(path: &str) -> Vec<(f64, f64, f64, Vec<i64>)> {
    let f = fs::File::open(path).unwrap_or_else(|_| panic!("ファイルが見つかりません: {}", path));
    let reader = BufReader::new(f);
    let mut records = Vec::new();
    for line in reader.lines() {
        let line = line.expect("読み込みエラー");
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.splitn(4, '\t').collect();
        if parts.len() < 3 {
            continue;
        }
        let t: f64 = parts[0].parse().unwrap_or(0.0);
        let x: f64 = parts[1].parse().unwrap_or(0.0);
        let y: f64 = parts[2].parse().unwrap_or(0.0);
        let items: Vec<i64> = if parts.len() >= 4 {
            parts[3]
                .split(',')
                .filter_map(|s| s.trim().parse().ok())
                .collect()
        } else {
            Vec::new()
        };
        if !items.is_empty() {
            records.push((t, x, y, items));
        }
    }
    records
}

// ---------------------------------------------------------------------------
// run サブコマンド
// ---------------------------------------------------------------------------

fn cmd_run(args: &HashMap<String, String>) {
    let input = args
        .get("input")
        .expect("--input PATH が必要です");

    let params = Md3DParams {
        bin_sizes: (
            args.get("dt").and_then(|s| s.parse().ok()).unwrap_or(1.0),
            args.get("dx").and_then(|s| s.parse().ok()).unwrap_or(1.0),
            args.get("dy").and_then(|s| s.parse().ok()).unwrap_or(1.0),
        ),
        window_bins: (
            args.get("wt").and_then(|s| s.parse().ok()).unwrap_or(5),
            args.get("wx").and_then(|s| s.parse().ok()).unwrap_or(3),
            args.get("wy").and_then(|s| s.parse().ok()).unwrap_or(3),
        ),
        threshold: args
            .get("threshold")
            .and_then(|s| s.parse().ok())
            .unwrap_or(3),
        max_length: args
            .get("max-length")
            .and_then(|s| s.parse().ok())
            .unwrap_or(3),
    };

    eprintln!("入力: {}", input);
    eprintln!("パラメータ: {:?}", params);

    let txns = read_tsv(input);
    eprintln!("トランザクション数: {}", txns.len());

    let t0 = Instant::now();
    let result = find_dense_itemsets_3d(&txns, &params);
    let elapsed = t0.elapsed();

    // 結果出力
    let mut patterns: Vec<&Vec<i64>> = result.keys().collect();
    patterns.sort();

    println!("# pattern\tn_regions\ttotal_cells");
    for pat in patterns {
        let regions = &result[pat];
        let total_cells: usize = regions.iter().map(|r| r.len()).sum();
        let pat_str: Vec<String> = pat.iter().map(|i| i.to_string()).collect();
        println!(
            "{}\t{}\t{}",
            pat_str.join(","),
            regions.len(),
            total_cells
        );
    }

    eprintln!(
        "\n検出パターン数: {}, 実行時間: {:.3}s",
        result.len(),
        elapsed.as_secs_f64()
    );
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

fn main() {
    let args = parse_args();
    match args.get("subcommand").map(|s| s.as_str()) {
        Some("gen") => cmd_gen(&args),
        Some("run") => cmd_run(&args),
        _ => {
            eprintln!("USAGE: md_pipeline <gen|run> [OPTIONS]");
            eprintln!("  gen --out PATH --n-txn N --seed S --n-items N --dense-regions N");
            eprintln!("  run --input PATH --dt F --dx F --dy F --wt N --wx N --wy N --threshold N --max-length N");
            std::process::exit(1);
        }
    }
}
