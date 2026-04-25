---
name: profile-dataset
description: ダウンロード済みデータセットの構造・統計・多次元AW適合性を調査する。新しいデータセットを実験に使う前の確認作業 / ビンサイズ・ウィンドウサイズの設計 / 論文記載用の統計表作成に使う。
---

# Skill: profile-dataset

## 0. Purpose

- **このSkillが解くタスク**: `dataset/<name>/` 配下の生データを調べ、多次元AW実験に向けたグリッド設計を提案する
- **使う場面**: 新データセットの初回調査 / ビンサイズ決定 / 論文の実験設定セクション用統計収集
- **できないこと**: 前処理スクリプトの作成・実験実行（それぞれ `impl-feature` / `run-experiment` スキルで行う）

---

## 1. Inputs

### 1.1 Required

- **データセットフォルダ**: `dataset/<name>/` のパス
- **生ファイル名**: CSVファイル名（例: `crime_latlon.csv`）

### 1.2 Optional

- **目標次元数 d**: 何次元グリッドにしたいか（デフォルト: ファイルの列から推定）
- **論文記載用**: 統計表を論文の実験設定セクション向けに整形するか

---

## 2. Outputs

- **プロファイルレポート**: `dataset/<name>/profile.md`
- **グリッド設計案**: ビンサイズ・次元数・推定セル数の提案

---

## 3. Procedure

### Step 1: ファイル構造確認

```sh
head -5 dataset/<name>/<file>.csv
wc -l dataset/<name>/<file>.csv
```

確認事項:
- 列名と型（時間列・緯度/経度列・アイテム列の特定）
- 行数（生イベント数）

### Step 2: 連続軸の統計

```python
import pandas as pd
df = pd.read_csv("dataset/<name>/<file>.csv", nrows=100000)
# 緯度・経度・深度等の統計
print(df[["latitude", "longitude"]].describe())
```

確認事項:
- min/max/mean/std
- NULL割合（`df.isnull().sum() / len(df)` ）
- 外れ値（lat/lonの場合は有効範囲 ±90/±180 外）

### Step 3: 時間軸の統計

```python
df["date"] = pd.to_datetime(df["time_col"])
print(df["date"].min(), df["date"].max())
print(f"期間: {(df['date'].max() - df['date'].min()).days} 日")
```

確認事項:
- 期間（日数・週数）
- 月ごとの件数分布（季節性の確認）

### Step 4: アイテム列の統計

```python
print(df["item_col"].value_counts().head(20))
print(f"ユニーク種類数: {df['item_col'].nunique()}")
```

確認事項:
- カテゴリ数（アイテム種類数）
- 上位20カテゴリとその件数
- 長尾分布か均一分布か

### Step 5: グリッド設計の提案

ビンサイズ候補を計算:

```python
lat_range = df["latitude"].max() - df["latitude"].min()
lon_range = df["longitude"].max() - df["longitude"].min()

for bin_deg in [0.005, 0.01, 0.02, 0.05, 0.1]:
    n_lat = int(lat_range / bin_deg) + 1
    n_lon = int(lon_range / bin_deg) + 1
    n_weeks = (期間の週数)
    n_cells = n_weeks * n_lat * n_lon
    print(f"bin={bin_deg:.3f}°: {n_lat}×{n_lon} spatial, {n_cells:,} total cells")
```

推奨ビンサイズの基準:
- 総グリッドセル数: 1万〜100万（多すぎると前処理メモリ圧迫）
- 各セルの平均イベント数: 0.5〜5（密すぎず疎すぎず）
- 空セル率: 50〜90%（実世界データとして妥当）

### Step 6: ウィンドウサイズの提案

```
W_t: 時間的まとまりのある単位（例: 4週=1ヶ月, 13週=1四半期）
W_x: 物理距離に対応（例: 0.02°×3=約6km の近傍）
θ:   ceil(W_t × W_x × W_y × 平均密度 × 0.5) 程度から開始
```

---

## 4. Output Format: profile.md

```markdown
# Dataset Profile: <name>

## 基本情報
- ファイル: <file>.csv
- 行数（生データ）: N件
- 期間: YYYY-MM-DD 〜 YYYY-MM-DD (N週)
- NULL率（緯度/経度）: N%

## 連続軸の統計
| 列 | min | max | mean | std |
|---|---|---|---|---|
| latitude | ... | ... | ... | ... |
| longitude | ... | ... | ... | ... |
| depth (あれば) | ... | ... | ... | ... |

## アイテム統計
- ユニーク種類数: N種
- 上位5カテゴリ: [(name, count), ...]

## グリッド設計案
| ビンサイズ | 緯度bins | 経度bins | 総セル数 | 平均イベント/セル | 推奨 |
|---|---|---|---|---|---|
| 0.01° | N | N | N | N | — |
| 0.02° | N | N | N | N | ★ |
| 0.05° | N | N | N | N | — |

## 推奨実験設定
- n_dims: d (時間 + 空間次元数)
- window: W_t=N, W_x=N, [W_y=N]
- threshold θ: N
- max_length: 2〜3
```

---

## 5. Quality Gates

- 全連続軸に NULL がないこと（or NULL率が5%未満）を確認済み
- 推奨グリッド設計で総セル数が 1万〜100万の範囲に入ること
- アイテム種類数が 5種以上あること（パターン探索の意味があるため）
- 軸が比例/順序尺度であることを再確認済み

---

## 6. Failure Modes & Fixes

- **NG1: 全体の NULL 率が高い（>20%）** → NULL行を除外した後の実効行数を再計算
- **NG2: アイテム種類が少ない（< 5種）** → アイテム列を変えるか、階層カテゴリを使う
- **NG3: グリッドセルが疎すぎる（平均 < 0.1 イベント/セル）** → ビンを大きくするか、期間を広げる
- **NG4: 時間粒度が粗い（日単位が最高解像度でも週100件未満）** → 月単位集計に切り替え
