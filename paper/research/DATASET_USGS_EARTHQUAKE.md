# Dataset: USGS Earthquake Catalog (ComCat)

## 概要

USGS（米国地質調査所）が公開する世界規模の地震カタログ。
多次元 Apriori-Window の**d=4 次元スケーラビリティ実証**および科学ドメインへの適用例として使用する。

| 項目 | 内容 |
|---|---|
| 提供元 | USGS Earthquake Hazards Program（ComCat） |
| URL | https://earthquake.usgs.gov/earthquakes/search/ |
| API | https://earthquake.usgs.gov/fdsnws/event/1/ |
| ライセンス | USGS Public Domain（研究・商用利用可、引用推奨） |
| 取得方式 | FDSN Web Service API（四半期ごとにページング） |
| ダウンロードスクリプト | `dataset/usgs_earthquake/download.py` |
| 前処理スクリプト | `paper/C-multidimensional/experiments/preprocess_usgs_earthquake.py` |

---

## 生データ仕様

| 列名 | 型 | 説明 |
|---|---|---|
| `time` | datetime（UTC） | 地震発生時刻（ISO 8601） |
| `latitude` | float | 震源緯度（WGS84） |
| `longitude` | float | 震源経度（WGS84） |
| `depth` | float (km) | 震源深度（0〜700 km） |
| `mag` | float | マグニチュード（M2.5 以上を取得） |

取得対象: M2.5 以上、2000-01-01 〜 2020-12-31（21年間）

---

## ダウンロード済みファイル

| ファイル | 行数 | 内容 |
|---|---|---|
| `dataset/usgs_earthquake/earthquakes.csv` | 545,666 行 | 生データ（世界全域、ヘッダ含む） |

---

## 地理的カバレッジ（全体）

| 項目 | 値 |
|---|---|
| 範囲 | 全世界（緯度 −83.9° 〜 87.1°、経度 ±180°） |
| 深度範囲 | 0 〜 735.8 km（有効範囲: 0〜700 km） |
| マグニチュード範囲 | 2.5 〜 8.4（平均 3.7） |
| 総件数 | 545,665 件 |

### 主要地域の件数（M2.5+、2000-2020）

| 地域 | bbox | 件数 |
|---|---|---|
| アラスカ | lat 54–72, lon −168–−140 | 44,683 |
| チリ | lat −56–−17, lon −76–−65 | 32,356 |
| カリフォルニア | lat 32–42, lon −124–−114 | 31,039 |
| 日本 | lat 24–46, lon 122–146 | 26,637 |
| イタリア | lat 36–48, lon 6–20 | 9,229 |
| トルコ | lat 35–43, lon 25–45 | 9,020 |

---

## 処理済みデータ（多次元AWグリッド）

### 3D: California（bin_size = 0.5°, マグニチュードバンドをアイテムに使用）

| 項目 | 値 |
|---|---|
| 次元構成 | 3D: week × lat\_bin × lon\_bin |
| グリッドサイズ | 1,096週 × 20 lat_bins × 20 lon_bins |
| 有効イベント数 | 30,224 件 |
| グリッドセル数 | 13,145 セル |
| 平均 items/cell | 1.17 |
| 出力 TSV | `experiments/data/usgs_eq_3d_california_blat0.5_blon0.5_t7d_itemsmag.tsv` |

### 4D: California（bin_size = 0.5°, depth_bin = 35 km）

| 項目 | 値 |
|---|---|
| 次元構成 | 4D: week × lat\_bin × lon\_bin × depth\_bin |
| グリッドサイズ | 1,096週 × 20 × 20 × 20 |
| グリッドセル数 | 13,151 セル |
| 出力 TSV | `experiments/data/usgs_eq_4d_california_blat0.5_blon0.5_t7d_itemsmag.tsv` |

### 軸の解釈

| 軸 | 意味 | 尺度 | ビン幅 |
|---|---|---|---|
| t | 週インデックス（2000-01-01 = 0） | 順序尺度 | 7日 |
| x | 緯度ビン（北方向に増加） | 比例尺度 | 0.5°（約 55 km） |
| y | 経度ビン（東方向に増加） | 比例尺度 | 0.5°（約 45 km） |
| z | 深度ビン（深い方向に増加） | 比例尺度 | 35 km（地震学的標準区分） |

---

## アイテム定義

### マグニチュードバンド（デフォルト: `--items mag`）

| ID | バンド | 地震学的意義 |
|---|---|---|
| 1 | M 2.5–3.0 | 微小地震（人体感知しにくい） |
| 2 | M 3.0–4.0 | 小地震（弱い揺れ） |
| 3 | M 4.0–5.0 | 中地震（物が揺れる） |
| 4 | M 5.0–6.0 | 強地震（建物被害の可能性） |
| 5 | M 6.0+ | 大地震 |

### 深度バンド（`--items depth`、サブダクションゾーン向け）

| ID | バンド | 地震学的区分 |
|---|---|---|
| 1 | 0–35 km | 浅発地震（地殻内） |
| 2 | 35–70 km | 上部マントル |
| 3 | 70–150 km | 中深発地震 |
| 4 | 150–300 km | 深発地震 |
| 5 | 300–700 km | 極深発地震 |

---

## 推奨実験パラメータ

```sh
# 3D California（スケーラビリティ確認用）
md_pipeline run \
  --input experiments/data/usgs_eq_3d_california_blat0.5_blon0.5_t7d_itemsmag.tsv \
  --n-dims 3 \
  --window 13,2,2 \
  --threshold 2 \
  --max-length 2
# → 約 10 パターン、0.5 秒（Apple M3）

# 4D California（d=4 次元スケーラビリティ実証）
md_pipeline run \
  --input experiments/data/usgs_eq_4d_california_blat0.5_blon0.5_t7d_itemsmag.tsv \
  --n-dims 4 \
  --window 13,2,2,2 \
  --threshold 2 \
  --max-length 2
```

---

## 実験での位置づけと限界

### 適した用途

| 実験 | 役割 |
|---|---|
| d=4 スケーラビリティ | **主目的**: 4次元実データで動作することを実証（time × lat × lon × depth） |
| 科学ドメイン適用例 | 都市犯罪以外の自然科学データへの汎用性を示す |

### 限界

| 問題 | 詳細 |
|---|---|
| アイテム空間の小ささ | マグニチュードバンドは 5 種のみ → max 10 通りの 2-item パターン |
| 平均 items/cell が低い | 1.17（Chicago の 7.59 と比べて疎） → 2-item 共起が少ない |
| パターン数が少ない | θ=2 で最大 10〜11 パターン（比較・アブレーション実験には不向き） |

> **結論**: パターン多様性の実験（アブレーション・比較）には Chicago Crime / NYPD / NYC 311 を使用し、USGS は d=4 の次元スケーラビリティ実証のみに使用する。

---

## 前処理オプション一覧

```sh
# デフォルト（California 3D, mag items, 0.5° bins）
python3 preprocess_usgs_earthquake.py

# 4D（California, depth bins）
python3 preprocess_usgs_earthquake.py --dims 4

# サブダクションゾーン（チリ, depth items, monthly）
python3 preprocess_usgs_earthquake.py \
  --region chile --items depth --time-bin 28 \
  --bin-lat 2.0 --bin-lon 2.0

# 利用可能な region: california, japan, alaska, chile
```
