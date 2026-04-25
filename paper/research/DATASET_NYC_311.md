# Dataset: NYC 311 Service Requests

## 概要

NYC Open Data が公開するニューヨーク市の 311 市民通報データ。市民が報告する非緊急サービスリクエスト（騒音、ごみ、熱水、道路問題等）を収録。
Chicago Crime / NYPD Crime とは異なる問題ドメイン（都市インフラ・生活環境）での汎化性検証に使用する。

| 項目 | 内容 |
|---|---|
| 提供元 | NYC Open Data（NYC DoITT） |
| URL | https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9 |
| ライセンス | NYC Open Data（研究・商用利用可） |
| 取得方式 | Socrata API（ページング、無登録） |
| ダウンロードスクリプト | `dataset/nyc_311/download.py` |
| 前処理スクリプト | `paper/C-multidimensional/experiments/preprocess_nyc_311.py` |

---

## 生データ仕様

| 列名 | 型 | 説明 |
|---|---|---|
| `created_date` | datetime | リクエスト受付日時（ISO 8601） |
| `complaint_type` | string | 通報種別（例: HEAT/HOT WATER, Noise - Residential） |
| `latitude` | float | 通報地点の緯度（WGS84） |
| `longitude` | float | 通報地点の経度（WGS84） |

取得対象: 2020-01-01 〜 2022-12-31（3年間）、座標 NULL 除外

> **注**: ダウンロードスクリプトが `year` フィールドで 2018-2022 を指定しているが、Socrata の `year` 列（クローズ年度）と `created_date` 年度の差異により実際には 2020-2022 年分が収録された。

---

## ダウンロード済みファイル

| ファイル | 行数 | 内容 |
|---|---|---|
| `dataset/nyc_311/requests.csv` | 9,132,215 行 | 生データ（2020-2022、ヘッダ含む） |

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
| グリッドサイズ | 157週 × 43 lat_bins × 58 lon_bins |
| 有効イベント数 | 9,132,214 件 |
| グリッドセル数 | 135,490 セル |
| 平均 items/cell | 18.14 |
| complaint 種別数 | 232 種 |
| 出力 TSV | `experiments/data/nyc_311_3d_bs0p010.tsv` |
| 出力メタ | `experiments/data/nyc_311_3d_bs0p010_meta.json` |

### 軸の解釈

| 軸 | 意味 | 尺度 | ビン幅 |
|---|---|---|---|
| t | 週インデックス（2018-01-01 = 0、実データは week 104〜260） | 順序尺度 | 7日 |
| x | 緯度ビン（北方向に増加） | 比例尺度 | 0.01°（約 1.1 km） |
| y | 経度ビン（東方向に増加） | 比例尺度 | 0.01°（約 0.9 km） |

---

## アイテム定義

232 種の通報種別（`complaint_type`）を 1-indexed の整数 ID にマッピング。

主要アイテム例（上位頻度、2020-2022）:

| ID | 通報種別 | 説明 |
|---|---|---|
| — | HEAT/HOT WATER | 暖房・温水不良（冬季に集中） |
| — | Noise - Residential | 住居騒音 |
| — | Blocked Driveway | 車道閉塞 |
| — | Illegal Parking | 違法駐車 |
| — | UNSANITARY CONDITION | 不衛生状況 |
| — | Street Light Condition | 街灯故障 |
| — | … | （全種別は `_meta.json` 参照） |

> 実際の ID は前処理時にアルファベット順でソートして付番される。`_meta.json` の `complaint_types` フィールドを参照。

---

## 推奨実験パラメータ

```sh
# アブレーション・比較実験（2020-2022 暫定 TSV）
md_pipeline run \
  --input experiments/data/nyc_311_3d_bs0p010.tsv \
  --n-dims 3 \
  --window 4,3,3 \
  --threshold 20 \
  --max-length 2
# → 2,828 パターン、132.8 秒（Apple M3）[2020-2022 部分データ]

# 高速設定（threshold 引き上げ）
md_pipeline run \
  --input experiments/data/nyc_311_3d_bs0p010.tsv \
  --n-dims 3 \
  --window 4,3,3 \
  --threshold 50 \
  --max-length 2
# → (未計測、約 500〜1,000 パターン見込み)
```

### 他データセットとの比較

| 項目 | Chicago Crime | NYPD Crime | NYC 311 |
|---|---|---|---|
| 対象都市 | シカゴ | ニューヨーク | ニューヨーク |
| ドメイン | 犯罪 | 犯罪 | 市民通報（非緊急） |
| 期間 | 2018–2022 | 2018–2022 | 2020–2022 |
| 生データ件数 | 1,168,412 件 | 2,317,293 件 | 9,132,214 件 |
| グリッドセル数 | 47,217 | 189,481 | 135,490 |
| item 種類数 | 33 種 | 69 種 | 232 種 |
| 平均 items/cell | 7.59 | 5.67 | 18.14 |
| 推奨 threshold | 3 | 5〜10 | 20〜50 |

> NYC 311 は item 種類数・平均 items/cell ともに最大であり、**最も密度の高いデータセット**。
> パターン多様性の評価（アブレーション上限確認）に最適。

---

## 実験での位置づけ

| 実験 | 役割 |
|---|---|
| EX-C アブレーション | Chicago Crime / NYPD Crime との速比・パターン数比較 |
| EX-D 比較実験 | 犯罪以外のドメイン（市民通報）での再現性検証 |
| N-スケーラビリティ | Chicago の約 8 倍規模での実行時間比較（最大スケール） |

---

## 利用上の注意

- 2010年以降のデータが存在するが、本実験では 2018-2022 の 5年分に統一（261週）
- Socrata API は降順（新→旧）で返却するため、ダウンロード途中のファイルは最近年のデータから収録される
- `complaint_type` は 200 種以上あり、粒度が粗いカテゴリ（GENERAL CONSTRUCTION）と細かいカテゴリ（Noise - Residential）が混在
- 座標は建物住所からジオコーディングされるため、同一住所の多数通報が同一 lat/lon に集中する場合あり
- `avg_items/cell` が高い（≈18）ため、threshold を低く設定するとパターン数が爆発的に増加する。EX-D では threshold ≥ 20 を推奨
- ダウンロード済み（9,132,215 行）。前処理済み TSV・meta は確定値

---

## 前処理オプション

```sh
# デフォルト（bin_size = 0.01°）
python3 preprocess_nyc_311.py

# 粗いグリッド（bin_size = 0.02°、Chicago Crime と同等）
python3 preprocess_nyc_311.py --bin-size 0.02
```
