---
name: find-dataset
description: 多次元 Apriori-Window 実験に使える公開データセットを探す。「新しいデータセットが欲しい」「実データで d=3 以上の実験がしたい」「論文に多様性を加えたい」ときに使う。
---

# Skill: find-dataset

## 0. Purpose

- **このSkillが解くタスク**: 多次元 Apriori-Window に適した公開データセットの発見・評価
- **使う場面**: 新しい実データ実験の立ち上げ / 論文への実データ多様性追加 / 特定の次元数（d=3以上）実験に使えるデータ探し
- **できないこと**: データのダウンロード・前処理・実験実行

---

## 1. 適合性の判定基準（必須）

多次元 AW 実験に使えるデータセットの条件：

| 軸 | 条件 | NG例 |
|----|------|------|
| **時間軸 t** | 日時・週・月インデックス（順序尺度） | — |
| **空間軸 x, y** | 緯度ビン・経度ビン・深度ビン等（比例尺度または等間隔順序尺度） | 警察区ID・店舗ID・国コード（名義尺度）|
| **アイテム列** | イベント種別・カテゴリ等（名義でOK） | — |

**スライディングウィンドウの意味**: `[b, b+W)` の範囲が「実際に近傍」でなければ密集が意味をなさない。名義尺度の軸では隣接セルが地理的に遠い可能性があり、検出された密集領域に解釈可能な意味が生まれない。

---

## 2. Inputs

### 2.1 Required

- **次元数 d**: 欲しいデータの次元数（例: d=2, d=3, d=4）
- **軸の種類**: 空間（lat/lon）か、それ以外（深度・気温・etc.）か

### 2.2 Optional

- **ドメイン**: 犯罪・地震・気象・SNS・小売など
- **規模感**: トランザクション数の目安（例: 1万〜100万件）
- **ライセンス制約**: 商用利用可 / 研究用のみ / 無制限

---

## 3. Procedure

1. **既存データセットの確認**
   - `dataset/` 配下の `download.py` を持つディレクトリを列挙
   - `dataset/<name>/README.md` があれば読んでスペックを確認

2. **候補検索**（WebSearch を使用）
   - 検索クエリ例:
     - `"open dataset" site:data.cityofchicago.org latitude longitude`
     - `USGS earthquake catalog CSV download latitude longitude`
     - `open data geospatial transaction dataset research`
   - 優先確認サイト:
     - Chicago Data Portal: `data.cityofchicago.org`
     - NYC Open Data: `data.cityofnewyork.us`
     - USGS: `earthquake.usgs.gov/fdsnws/event/1/`
     - NOAA / JMA（気象・地震）
     - Stanford SNAP（ソーシャルデータ）

3. **適合性評価**（各候補について）
   - 列一覧を確認し、lat/lon or 連続軸の存在を確認
   - 行数・期間・ライセンスを確認
   - グリッド変換案を記述: `t軸=?, x軸=?, y軸=?, アイテム=?`
   - 適合性スコア: ◎/○/△/✗ + 理由

4. **既存データとの比較**
   - `dataset/` に既にあるものと重複しないか
   - 論文の実験構成（EX-B合成, EX-C/D実データ）で何を補完するか

5. **結果をレポート**
   - 表形式で候補を整理（名前・URL・軸構成・規模・適合性）
   - 優先順位を付けてダウンロード推奨順を提示

---

## 4. Quality Gates

- 推奨データセットの全軸が比例/順序尺度であることを確認済みであること
- ダウンロードURLまたはAPI endpointが実在することをWebFetchで確認済みであること
- アイテム列が存在し、多様なカテゴリを持つことを確認済みであること
- 既存 `dataset/` との重複がないこと

---

## 5. 既知の適合データセット（参照用）

| データセット | フォルダ | 軸構成 | アイテム | 規模 | 状態 |
|---|---|---|---|---|---|
| Chicago Crime (lat/lon版) | `dataset/chicago_crime/` | week × lat_bin × lon_bin | 犯罪種別 32種 | ~120万件 | ダウンロード中 |
| USGS Earthquake | `dataset/usgs_earthquake/` | week × lat_bin × lon_bin (× depth_bin) | マグニチュード帯 | ~55万件 | ダウンロード中 |
| NYC 311 Requests | `dataset/nyc_311/` | week × lat_bin × lon_bin | complaint type | ~900万件 | ダウンロード中 |
| NYPD Complaint | `dataset/nyc_crime/` | week × lat_bin × lon_bin | 犯罪種別 | ~230万件 | ダウンロード中 |

---

## 6. Failure Modes & Fixes

- **NG1: 軸が名義尺度だった** → lat/lon ビン化 or 連続変数での代替軸を検討
- **NG2: データが非公開・有償** → Kaggle or UCI ML Repository で類似データを検索
- **NG3: 規模が小さすぎる（< 1,000 セル）** → ビンサイズを細かくするか、期間を延長
