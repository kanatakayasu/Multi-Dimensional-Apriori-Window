//! 多次元 Apriori-Window CLI バイナリ
//!
//! USAGE:
//!   md_pipeline gen  --out PATH --n-txn N [OPTIONS]
//!   md_pipeline run  --input PATH [OPTIONS]
//!
//! GEN OPTIONS:
//!   --out PATH        出力ファイル（TSV: t x y items...）
//!   --n-txn N         トランザクション数（デフォルト 5000）; --lambda 指定時は無視
//!   --lambda F        密度ベース生成: 各グリッドセルの平均トランザクション数 (Poisson)
//!   --p-item F        各アイテムをトランザクションに含む確率（デフォルト 0.15）; --lambda 指定時のみ有効
//!   --seed S          乱数シード（デフォルト 42）
//!   --n-items N       アイテム種類数（デフォルト 20）
//!   --dense-regions N 植え付け密集領域数（デフォルト 3）; --lambda 非指定時のみ有効
//!   --n-dims N        次元数（デフォルト 3）
//!   --space-max F     各空間次元の最大値（デフォルト 50.0）
//!   --t-max F         時間軸の最大値（デフォルト 100.0）
//!
//! RUN OPTIONS:
//!   --input PATH      入力 TSV ファイル
//!   --n-dims N        次元数（デフォルト 3、3以外は ND パスを使用）
//!   --dt F            t ビン幅（デフォルト 1.0）
//!   --dx F            x ビン幅（デフォルト 1.0）
//!   --dy F            y ビン幅（デフォルト 1.0）
//!   --bin-size F,...  全次元共通ビン幅（コンマ区切り、--n-dims と同数）
//!   --wt N            t ウィンドウビン数（デフォルト 5）
//!   --wx N            x ウィンドウビン数（デフォルト 3）
//!   --wy N            y ウィンドウビン数（デフォルト 3）
//!   --window N,...    全次元共通ウィンドウビン数（コンマ区切り、--n-dims と同数）
//!   --threshold N     サポート閾値（デフォルト 3）
//!   --max-length N    実験用の最大パターン長（省略時は無制限）
//!   --prefix-sum      互換性のため残している legacy flag（現行 interval-based 実装では no-op）
//!   --no-t-stride     t軸ストライドを無効化（アブレーション用）
//!   --no-apriori-prune Apriori枝刈りを無効化（アブレーション用）

use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::time::Instant;

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rand_distr::{Distribution, Poisson};

use apriori_window_md::md_apriori::{
    find_dense_itemsets_3d, find_dense_itemsets_nd, DenseRegion, Md3DParams, MdNDParams,
};

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
    let seed: u64 = args.get("seed").and_then(|s| s.parse().ok()).unwrap_or(42);
    let n_items: usize = args
        .get("n-items")
        .and_then(|s| s.parse().ok())
        .unwrap_or(20);
    let n_dims: usize = args.get("n-dims").and_then(|s| s.parse().ok()).unwrap_or(3);

    assert!(n_dims >= 1, "--n-dims は 1 以上が必要です");

    let mut rng = StdRng::seed_from_u64(seed);
    let t_max: usize = args
        .get("t-max")
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);
    let space_max: usize = args
        .get("space-max")
        .and_then(|s| s.parse().ok())
        .unwrap_or(50);
    let space_dims = n_dims - 1; // 空間次元数

    // --lambda が指定された場合は密度ベース生成（Poisson）
    if let Some(lambda_str) = args.get("lambda") {
        let lambda: f64 = lambda_str
            .parse()
            .expect("--lambda は浮動小数点数で指定してください");
        let p_item: f64 = args
            .get("p-item")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.15);

        assert!(lambda > 0.0, "--lambda は正の値が必要です");
        assert!(
            p_item > 0.0 && p_item <= 1.0,
            "--p-item は (0, 1] の範囲で指定してください"
        );

        let poisson = Poisson::new(lambda).expect("Poisson 分布の初期化失敗");

        let mut records: Vec<(Vec<f64>, Vec<i64>)> = Vec::new();

        // 全グリッドセルをイテレート: t ∈ [0, t_max), xi ∈ [0, space_max)
        // 多次元インデックス生成: t 軸 + (d-1) 空間軸
        let mut cell_coords: Vec<usize> = vec![0usize; n_dims];
        'outer: loop {
            // t 軸: cell_coords[0], 空間軸: cell_coords[1..]
            let k: u64 = poisson.sample(&mut rng) as u64;
            for _ in 0..k {
                // 各トランザクションはセル内のランダム位置（整数座標 = セル番号）
                let coords: Vec<f64> = cell_coords.iter().map(|&c| c as f64).collect();
                // アイテムを独立 Bernoulli で決定
                let items: Vec<i64> = (1..=(n_items as i64))
                    .filter(|_| rng.gen::<f64>() < p_item)
                    .collect();
                if !items.is_empty() {
                    records.push((coords, items));
                }
            }

            // インクリメント（最下位次元から）
            let mut dim = n_dims - 1;
            loop {
                cell_coords[dim] += 1;
                let limit = if dim == 0 { t_max } else { space_max };
                if cell_coords[dim] < limit {
                    break;
                }
                cell_coords[dim] = 0;
                if dim == 0 {
                    break 'outer;
                }
                dim -= 1;
            }
        }

        // 書き出し
        let mut f = fs::File::create(out).expect("出力ファイル作成失敗");
        let coord_headers: Vec<String> = std::iter::once("t".to_string())
            .chain((1..n_dims).map(|i| format!("x{}", i)))
            .collect();
        writeln!(f, "# {}\titems...", coord_headers.join("\t")).unwrap();

        for (coords, items) in &records {
            let coords_str: Vec<String> = coords.iter().map(|c| format!("{:.3}", c)).collect();
            let items_str: Vec<String> = items.iter().map(|i| i.to_string()).collect();
            writeln!(f, "{}\t{}", coords_str.join("\t"), items_str.join(",")).unwrap();
        }

        let total_cells: usize = t_max * space_max.pow(space_dims as u32);
        let expected_n =
            (lambda * total_cells as f64 * (1.0 - (1.0 - p_item).powi(n_items as i32))) as usize;
        eprintln!(
            "密度ベース生成完了: {} 件 → {} (次元数={}, λ={}, p_item={}, セル数={}, 期待N≈{})",
            records.len(),
            out,
            n_dims,
            lambda,
            p_item,
            total_cells,
            expected_n
        );
        return;
    }

    // --lambda 非指定: 従来の植え込みパターン方式
    let n_txn: usize = args
        .get("n-txn")
        .and_then(|s| s.parse().ok())
        .unwrap_or(5000);
    let n_dense: usize = args
        .get("dense-regions")
        .and_then(|s| s.parse().ok())
        .unwrap_or(3);

    let t_max_f = t_max as f64;
    let space_max_f = space_max as f64;

    // 密集領域の中心を決定（margin を space_max に応じて調整）
    let t_margin = (t_max_f * 0.1).max(2.0);
    let s_margin = (space_max_f * 0.1).max(1.0);
    let dense_centers: Vec<(f64, Vec<f64>, Vec<i64>)> = (0..n_dense)
        .map(|i| {
            let tc_lo = t_margin;
            let tc_hi = (t_max_f - t_margin).max(tc_lo + 1.0);
            let tc = rng.gen_range(tc_lo..tc_hi);
            let s_lo = s_margin;
            let s_hi = (space_max_f - s_margin).max(s_lo + 1.0);
            let sc: Vec<f64> = (0..space_dims).map(|_| rng.gen_range(s_lo..s_hi)).collect();
            let item_a = (i * 2 + 1) as i64;
            let item_b = (i * 2 + 2) as i64;
            (tc, sc, vec![item_a, item_b])
        })
        .collect();

    // 密集トランザクションを植え付け（各領域に 20 件）
    let mut records: Vec<(Vec<f64>, Vec<i64>)> = Vec::new();
    for (tc, sc, items) in &dense_centers {
        for _ in 0..20 {
            let t = tc + rng.gen_range(-2.0..2.0);
            let mut coords = vec![t.max(0.0)];
            for &sc_k in sc {
                coords.push((sc_k + rng.gen_range(-1.0..1.0)).max(0.0));
            }
            records.push((coords, items.clone()));
        }
    }

    // バックグラウンドノイズ
    while records.len() < n_txn {
        let mut coords = vec![rng.gen_range(0.0..t_max_f)];
        for _ in 0..space_dims {
            coords.push(rng.gen_range(0.0..space_max_f));
        }
        let n = rng.gen_range(1..=4);
        let items: Vec<i64> = (0..n).map(|_| rng.gen_range(1..=n_items as i64)).collect();
        records.push((coords, items));
    }

    // 書き出し（ヘッダ）
    let mut f = fs::File::create(out).expect("出力ファイル作成失敗");
    let coord_headers: Vec<String> = std::iter::once("t".to_string())
        .chain((1..n_dims).map(|i| format!("x{}", i)))
        .collect();
    writeln!(f, "# {}\titems...", coord_headers.join("\t")).unwrap();

    for (coords, items) in &records {
        let coords_str: Vec<String> = coords.iter().map(|c| format!("{:.3}", c)).collect();
        let items_str: Vec<String> = items.iter().map(|i| i.to_string()).collect();
        writeln!(f, "{}\t{}", coords_str.join("\t"), items_str.join(",")).unwrap();
    }

    eprintln!(
        "生成完了: {} 件 → {} (次元数={})",
        records.len(),
        out,
        n_dims
    );
    eprintln!("植え付け密集領域:");
    for (i, (tc, sc, items)) in dense_centers.iter().enumerate() {
        eprintln!(
            "  Region {}: t={:.1} space={:?} items={:?}",
            i + 1,
            tc,
            sc,
            items
        );
    }
}

// ---------------------------------------------------------------------------
// 入力ファイル読み込み
// ---------------------------------------------------------------------------

/// 3D 固定フォーマット読み込み（後方互換用）
fn read_tsv(path: &str) -> Vec<(f64, f64, f64, Vec<i64>)> {
    let f = fs::File::open(path).unwrap_or_else(|_| panic!("ファイルが見つかりません: {path}"));
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

/// N 次元フォーマット読み込み（タブ区切り: coord0 coord1 ... coord_{n-1} items）
fn read_tsv_nd(path: &str, n_dims: usize) -> Vec<(Vec<f64>, Vec<i64>)> {
    let f = fs::File::open(path).unwrap_or_else(|_| panic!("ファイルが見つかりません: {path}"));
    let reader = BufReader::new(f);
    let mut records = Vec::new();
    for line in reader.lines() {
        let line = line.expect("読み込みエラー");
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        // n_dims 座標 + 1 アイテムカラム
        let parts: Vec<&str> = line.splitn(n_dims + 1, '\t').collect();
        if parts.len() < n_dims {
            continue;
        }
        let coords: Vec<f64> = parts[..n_dims]
            .iter()
            .map(|s| s.parse().unwrap_or(0.0))
            .collect();
        let items: Vec<i64> = if parts.len() > n_dims {
            parts[n_dims]
                .split(',')
                .filter_map(|s| s.trim().parse().ok())
                .collect()
        } else {
            Vec::new()
        };
        if !items.is_empty() {
            records.push((coords, items));
        }
    }
    records
}

// ---------------------------------------------------------------------------
// run サブコマンド
// ---------------------------------------------------------------------------

fn cmd_run(args: &HashMap<String, String>) {
    let input = args.get("input").expect("--input PATH が必要です");

    let n_dims: usize = args.get("n-dims").and_then(|s| s.parse().ok()).unwrap_or(3);

    assert!(n_dims >= 1, "--n-dims は 1 以上が必要です");

    let threshold: usize = args
        .get("threshold")
        .and_then(|s| s.parse().ok())
        .unwrap_or(3);
    let max_length = args.get("max-length").and_then(|s| s.parse().ok());

    eprintln!("入力: {input}  次元数: {n_dims}");

    // n_dims == 3 かつ --bin-size / --window オプション未指定の場合は既存 3D パスを使用
    if n_dims == 3 && args.get("bin-size").is_none() && args.get("window").is_none() {
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
            threshold,
            max_length,
        };

        eprintln!("パラメータ (3D): {params:?}");

        let txns = read_tsv(input);
        eprintln!("トランザクション数: {}", txns.len());

        let t0 = Instant::now();
        let result = find_dense_itemsets_3d(&txns, &params);
        let elapsed = t0.elapsed();

        print_results_3d(&result, elapsed);
    } else {
        // ND パス
        // ビン幅: --bin-size または --dt/dx/... デフォルト 1.0
        let bin_sizes: Vec<f64> = if let Some(s) = args.get("bin-size") {
            s.split(',').filter_map(|x| x.trim().parse().ok()).collect()
        } else {
            vec![1.0f64; n_dims]
        };
        let window_bins: Vec<usize> = if let Some(s) = args.get("window") {
            s.split(',').filter_map(|x| x.trim().parse().ok()).collect()
        } else {
            // デフォルト: t=5, space=3
            let mut w = vec![3usize; n_dims];
            w[0] = 5;
            w
        };

        assert_eq!(
            bin_sizes.len(),
            n_dims,
            "--bin-size の要素数が --n-dims と一致しません"
        );
        assert_eq!(
            window_bins.len(),
            n_dims,
            "--window の要素数が --n-dims と一致しません"
        );

        // 互換性のため保持。現行 interval-based 実装では未使用。
        let use_prefix_sum = args.get("prefix-sum").is_some();
        let params = MdNDParams {
            bin_sizes,
            window_bins,
            threshold,
            max_length,
            use_prefix_sum,
            use_binsearch: !use_prefix_sum,
            use_t_stride: args.get("no-t-stride").is_none(),
            use_apriori_prune: args.get("no-apriori-prune").is_none(),
        };

        eprintln!("パラメータ (ND): {params:?}");

        let txns = read_tsv_nd(input, n_dims);
        eprintln!("トランザクション数: {}", txns.len());

        let t0 = Instant::now();
        let result = find_dense_itemsets_nd(&txns, &params);
        let elapsed = t0.elapsed();

        print_results_nd(&result, elapsed);
    }
}

fn print_results_3d(
    result: &std::collections::HashMap<Vec<i64>, Vec<DenseRegion>>,
    elapsed: std::time::Duration,
) {
    let mut patterns: Vec<&Vec<i64>> = result.keys().collect();
    patterns.sort();

    println!("# pattern\tn_slices\ttotal_intervals\ttotal_span");
    for pat in patterns {
        let slices = &result[pat];
        let total_intervals: usize = slices.iter().map(|slice| slice.intervals.len()).sum();
        let total_span: usize = slices
            .iter()
            .flat_map(|slice| slice.intervals.iter())
            .map(|(start, end)| end.saturating_sub(*start) + 1)
            .sum();
        let pat_str: Vec<String> = pat.iter().map(|i| i.to_string()).collect();
        println!(
            "{}\t{}\t{}\t{}",
            pat_str.join(","),
            slices.len(),
            total_intervals,
            total_span
        );
    }

    eprintln!(
        "\n検出パターン数: {}, 実行時間: {:.3}s",
        result.len(),
        elapsed.as_secs_f64()
    );
}

fn print_results_nd(
    result: &std::collections::HashMap<Vec<i64>, Vec<DenseRegion>>,
    elapsed: std::time::Duration,
) {
    let mut patterns: Vec<&Vec<i64>> = result.keys().collect();
    patterns.sort();

    println!("# pattern\tn_slices\ttotal_intervals\ttotal_span");
    for pat in patterns {
        let slices = &result[pat];
        let total_intervals: usize = slices.iter().map(|slice| slice.intervals.len()).sum();
        let total_span: usize = slices
            .iter()
            .flat_map(|slice| slice.intervals.iter())
            .map(|(start, end)| end.saturating_sub(*start) + 1)
            .sum();
        let pat_str: Vec<String> = pat.iter().map(|i| i.to_string()).collect();
        println!(
            "{}\t{}\t{}\t{}",
            pat_str.join(","),
            slices.len(),
            total_intervals,
            total_span
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
            eprintln!(
                "  gen --out PATH --n-txn N --seed S --n-items N --dense-regions N --n-dims N"
            );
            eprintln!("  run --input PATH --n-dims N [--dt F --dx F --dy F | --bin-size F,...] [--wt N --wx N --wy N | --window N,...] --threshold N [--max-length N] [--prefix-sum (legacy/no-op)] [--no-t-stride] [--no-apriori-prune]");
            std::process::exit(1);
        }
    }
}
