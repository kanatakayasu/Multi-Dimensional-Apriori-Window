# Dataset: NYPD Complaint Data Historic

## 概要

NYC Open Data が公開するニューヨーク市の NYPD 犯罪通報データ。
Chicago Crime と同一問題設定（都市犯罪 × lat/lon グリッド）で**再現性・汎化性の検証**に使用する。

| 項目 | 内容 |
|---|---|
| 提供元 | NYC Open Data（NYPD） |
| URL | https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i |
| ライセンス | NYC Open Data（研究・商用利用可） |
| 取得方式 | Socrata API（ページング、無登録） |
| ダウンロードスクリプト | `dataset/nyc_crime/download.py` |
| 前処理スクリプト | `paper/C-multidimensional/experiments/preprocess_nyc_crime.py` |

---

## 生データ仕様

| 列名 | 型 | 説明 |
|---|---|---|
| `cmplnt_fr_dt` | datetime | 犯罪発生日時（ISO 8601） |
| `ofns_desc` | string | 犯罪種別（Offense Description, 約 69 種） |
| `latitude` | float | 犯罪発生地点の緯度（WGS84） |
| `longitude` | float | 犯罪発生地点の経度（WGS84） |

取得対象: 2018-01-01 〜 2022-12-31（5年間）

---

## ダウンロード済みファイル

| ファイル | 行数 | 内容 |
|---|---|---|
| `dataset/nyc_crime/complaints.csv` | 2,317,295 行 | 生データ（ヘッダ含む） |

---

## 地理的カバレッジ

| 項目 | 値 |
|---|---|
| 都市 | ニューヨーク市（ニューヨーク州、米国） |
| 緯度範囲 | 40.49° 〜 40.92° N |
| 経度範囲 | −74.27° 〜 −73.69° W |
| 面積（概算） | 約 47 km × 52 km（5区全域） |

---

## 処理済みデータ（多次元AWグリッド）

### デフォルト設定（bin_size = 0.01°）

| 項目 | 値 |
|---|---|
| 次元構成 | 3D: week × lat\_bin × lon\_bin |
| グリッドサイズ | 261週 × 43 lat_bins × 58 lon_bins |
| 有効イベント数 | 2,317,293 件（ほぼ全件） |
| グリッドセル数 | 189,481 セル |
| 平均 items/cell | 5.67 |
| 出力 TSV | `experiments/data/nyc_crime_3d_bs0p010.tsv` |
| 出力メタ | `experiments/data/nyc_crime_3d_bs0p010_meta.json` |

### 軸の解釈

| 軸 | 意味 | 尺度 | ビン幅 |
|---|---|---|---|
| t | 週インデックス（2018-01-01 = 0） | 順序尺度 | 7日 |
| x | 緯度ビン（北方向に増加） | 比例尺度 | 0.01°（約 1.1 km） |
| y | 経度ビン（東方向に増加） | 比例尺度 | 0.01°（約 0.9 km） |

---

## アイテム定義

69 種の犯罪種別（`ofns_desc`）を 1-indexed の整数 ID にマッピング。

主要アイテム例（上位頻度）:

| ID | 犯罪種別 |
|---|---|
| 28 | GRAND LARCENY |
| 58 | PETIT LARCENY |
| 15 | DANGEROUS DRUGS |
| 21 | FELONY ASSAULT |
| 8 | ASSAULT 3 & RELATED OFFENSES |
| 63 | ROBBERY |
| 13 | CRIMINAL MISCHIEF & RELATED OF |
| … | （全 69 種、`_meta.json` 参照） |

---

## 推奨実験パラメータ

```sh
# アブレーション・比較実験
md_pipeline run \
  --input experiments/data/nyc_crime_3d_bs0p010.tsv \
  --n-dims 3 \
  --window 4,3,3 \
  --threshold 5 \
  --max-length 2
# → 601 パターン、38.7 秒（Apple M3）

# 高速設定（threshold 緩和）
md_pipeline run \
  --input experiments/data/nyc_crime_3d_bs0p010.tsv \
  --n-dims 3 \
  --window 4,3,3 \
  --threshold 10 \
  --max-length 2
# → 343 パターン、20.9 秒（Apple M3）
```

### Chicago Crime との比較

| 項目 | Chicago Crime | NYPD Crime |
|---|---|---|
| 対象都市 | シカゴ（人口 270 万） | ニューヨーク（人口 840 万） |
| 期間 | 2018–2022 | 2018–2022 |
| 生データ件数 | 1,168,412 件 | 2,317,293 件 |
| グリッドセル数 | 47,217 | 189,481 |
| item 種類数 | 33 種 | 69 種 |
| 平均 items/cell | 7.59 | 5.67 |
| 推奨 threshold | 3 | 5〜10 |

---

## 実験での位置づけ

| 実験 | 役割 |
|---|---|
| EX-C アブレーション | Chicago Crime との速比・パターン数の比較対象 |
| EX-D 比較実験 | Chicago Crime と独立した別都市での再現性検証 |
| N-スケーラビリティ | Chicago の約 2 倍の規模での実行時間比較 |
