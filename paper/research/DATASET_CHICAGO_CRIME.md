# Dataset: Chicago Crime (Crimes 2001 to Present)

## 概要

Chicago Data Portal が公開するシカゴ市内の犯罪通報データ。
多次元 Apriori-Window 実験の**主要実データ**として使用する。

| 項目 | 内容 |
|---|---|
| 提供元 | City of Chicago Open Data Portal |
| URL | https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2 |
| ライセンス | City of Chicago Open Data License（研究・商用利用可） |
| 取得方式 | Socrata API（ページング、無登録） |
| ダウンロードスクリプト | `dataset/chicago_crime/download.py` |
| 前処理スクリプト | `paper/C-multidimensional/experiments/preprocess_chicago_crime.py` |

---

## 生データ仕様

| 列名 | 型 | 説明 |
|---|---|---|
| `date` | datetime | 犯罪発生日時（ISO 8601） |
| `primary_type` | string | 犯罪種別（Primary Type, 例: THEFT, BATTERY） |
| `latitude` | float | 犯罪発生地点の緯度（WGS84） |
| `longitude` | float | 犯罪発生地点の経度（WGS84） |

取得対象: 2018-01-01 〜 2022-12-31（5年間）

---

## ダウンロード済みファイル

| ファイル | 行数 | サイズ | 内容 |
|---|---|---|---|
| `dataset/chicago_crime/crime_latlon.csv` | 1,168,417 行 | — | 生データ（ヘッダ含む） |

---

## 地理的カバレッジ

| 項目 | 値 |
|---|---|
| 都市 | シカゴ（イリノイ州、米国） |
| 緯度範囲 | 41.64° 〜 42.04° N |
| 経度範囲 | −87.94° 〜 −87.52° W |
| 面積（概算） | 約 44 km × 37 km（外れ値 4 件除外） |

---

## 処理済みデータ（多次元AWグリッド）

### デフォルト設定（bin_size = 0.02°）

| 項目 | 値 |
|---|---|
| 次元構成 | 3D: week × lat\_bin × lon\_bin |
| グリッドサイズ | 261週 × 20 lat_bins × 21 lon_bins |
| 有効イベント数 | 1,168,412 件（外れ値 4 件除外） |
| グリッドセル数 | 47,217 セル |
| 平均 items/cell | 7.59 |
| 出力 TSV | `experiments/data/chicago_crime_3d_bs0p020.tsv` |
| 出力メタ | `experiments/data/chicago_crime_3d_bs0p020_meta.json` |

### 軸の解釈

| 軸 | 意味 | 尺度 | ビン幅 |
|---|---|---|---|
| t | 週インデックス（2018-01-01 = 0） | 順序尺度 | 7日 |
| x | 緯度ビン（北方向に増加） | 比例尺度 | 0.02°（約 2.2 km） |
| y | 経度ビン（東方向に増加） | 比例尺度 | 0.02°（約 1.6 km） |

> **重要**: すべての軸が順序/比例尺度であり、スライディングウィンドウ近傍 = 地理的近傍が成立する。
> 旧バージョン（警察区 ID を x 軸に使用）は名義尺度であったため廃止。

---

## アイテム定義

33 種の犯罪種別（`primary_type`）を 1-indexed の整数 ID にマッピング。

| ID | 犯罪種別 | ID | 犯罪種別 |
|---|---|---|---|
| 1 | ARSON | 18 | MOTOR VEHICLE THEFT |
| 2 | ASSAULT | 19 | NARCOTICS |
| 3 | BATTERY | 20 | NON-CRIMINAL |
| 4 | BURGLARY | 24 | OTHER OFFENSE |
| 7 | CRIMINAL DAMAGE | 29 | ROBBERY |
| 12 | HOMICIDE | 31 | THEFT |
| 19 | NARCOTICS | 33 | WEAPONS VIOLATION |
| … | （全 33 種、`_meta.json` 参照） | | |

---

## 推奨実験パラメータ

```sh
# アブレーション・比較実験（EX-C / EX-D 相当）
md_pipeline run \
  --input experiments/data/chicago_crime_3d_bs0p020.tsv \
  --n-dims 3 \
  --window 4,3,3 \
  --threshold 3 \
  --max-length 2
# → 382 パターン、6.5 秒（Apple M3）
```

### パラメータの根拠

| パラメータ | 値 | 根拠 |
|---|---|---|
| `--window 4,3,3` | 4週 × 3lat × 3lon | 約1ヶ月 × 約6km²の近傍 |
| `--threshold 3` | 3 | 平均 7.59 items/cell を考慮し、パターンが多すぎない閾値 |
| `--max-length 2` | 2 | 2-item パターンまで（3-item は計算コスト高） |

---

## 利用上の注意

- 2018年以前のデータもAPIで取得可能だが、本実験では5年分（261週）に統一
- 外れ値（シカゴ市外の座標）が4件存在し、前処理で除外済み
- `CRIM SEXUAL ASSAULT` と `CRIMINAL SEXUAL ASSAULT` が別種として存在（元データの表記ゆれ）
- ダウンロードは1回あたり約10分（約120万件、Socrata API 50K件/ページ）

---

## 実験での位置づけ

| 実験 | 役割 |
|---|---|
| EX-B スケーラビリティ | 合成データの比較基準（実データとの実行時間対比） |
| EX-C アブレーション | **主実験データ**（full / -PS / -TS / -AP の速比測定） |
| EX-D 比較実験 | **主実験データ**（vs MZoom\_2D の精度・速度比較） |
