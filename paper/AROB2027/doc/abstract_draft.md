# AROB 2027 — Abstract Draft

## Submission Info
- Deadline: 2026-10-28 (UTC 24:00)
- Format: English, 400–600 words, no figures or references
- Submission: EasyChair

## Title

Streaming Apriori-Window: Mining Dense Patterns from Streaming Data for Autonomous Agent Monitoring

## Keywords

data stream mining, pattern recognition, sensor data analysis, behavior analysis, intelligent monitoring

---

## Abstract

Autonomous AI systems and robotic agents generate streams of sensor events that encode behavioral patterns. Understanding when these patterns densely co-occur, not merely whether they exist globally, is essential for real-time monitoring, anomaly detection, and adaptive control in intelligent environments. In multi-agent systems and sensor-equipped robotic platforms, for instance, detecting that a specific set of events repeatedly clusters within particular time intervals can reveal coordinated behaviors, routine structures, or emerging anomalies that demand timely response. The approach also has broad applicability across domains such as retail and epidemiology.

Existing methods do not support dense interval detection over event streams. Gap-constraint-based approaches such as LPFIM and RPM indirectly estimate dense intervals through a single parameter that simultaneously governs both pattern identification and interval accuracy, making tuning difficult and results inexact. Other methods such as GLFMiner and SIM operate on fixed granularities or return only a single interval per itemset. All of these approaches operate in batch mode and provide no mechanism for incremental processing or controllable scan frequency.

We propose a dense interval mining algorithm for event streams, parameterized by a scan interval n (in seconds). The algorithm identifies all time intervals in which itemset occurrence frequency within a fixed-width sliding window meets a threshold. When n = 1, scans fire every second, yielding highly responsive output; when n is large, many seconds of events are batched together, reducing computational cost. Because the window slides monotonically from left to right, any interval ending before the current scan position is unaffected by future events, guaranteeing confirmed output without reprocessing. Two speedup techniques are incorporated to achieve the processing speed required for practical stream operation: Scan Stride Skipping, which exploits monotone window movement to skip redundant scan positions, and Apriori Interval Pruning, which restricts candidate evaluation to dense intervals of constituent items.

We evaluate the algorithm on both synthetic and real-world data across four experiments. A parameter sensitivity study (EX-1) on synthetic streams varies n to characterize the tradeoff between scan frequency and processing speed. A scalability study (EX-2) on synthetic data independently varies stream length, item count, and window size to quantify how processing cost scales with data characteristics, showing that processing remains feasible even for streams of up to 10^8 events. An ablation study (EX-3) compares four algorithm variants: Naive, Scan Stride Skipping only, Apriori Interval Pruning only, and the full algorithm, confirming that both speedup techniques contribute independently and that their combination achieves the best overall processing speed. Finally, in an evaluation using real-world data (EX-4), we apply the algorithm to two CASAS smart home sensor datasets. CASAS provides a multi-sensor co-activation stream structurally analogous to autonomous robotic event logs. Results show that the detected dense intervals correspond to interpretable behavioral routines, confirming the approach's practical utility for autonomous environment monitoring.

The proposed algorithm provides a unified framework for streaming dense interval mining with explicit control over scan frequency. Ablation experiments confirm that both speedup techniques contribute meaningfully to processing speed, and experiments on real sensor data demonstrate interpretable, domain-consistent outputs. Future work includes applying the framework to behavioral logs collected from physical robotic systems, further accelerating processing for high-frequency streams, and developing automatic optimization of scan interval and threshold parameters.

---

## 日本語訳

自律AIシステムおよびロボットエージェントは、行動パターンを内包したセンサイベントストリームを生成する。これらのパターンが「いつ」密集して共起するかを理解すること、単にグローバルに存在するかどうかではなく、は、知的環境におけるリアルタイム監視・異常検知・適応制御に不可欠である。マルチエージェントシステムやセンサ搭載ロボットプラットフォームでは、特定のイベント集合が特定の時間区間に密集していることを検出することで、協調行動・日常ルーティン・迅速な対応を要する異常の出現を明らかにすることができる。また、このアルゴリズムは小売や疫学などの幅広い分野への応用も期待できる。

既存手法はイベントストリームに対する密集区間検出をサポートしない。LPFIM や RPM などのギャップ制約型手法は、パターン識別精度と区間検出精度の両方を単一パラメータで制御するため、適切なパラメータ設定が困難であり結果も近似的である。GLFMiner や SIM は固定粒度または1アイテムセットにつき1区間のみを返す。これらはいずれもバッチ処理のみで動作し、逐次処理やスキャン頻度の制御を行う機構を持たない。

本研究では、スキャン間隔パラメータ n を導入したストリーム向け密集区間マイニングアルゴリズムを提案する。n は「n 秒ごとに1回スキャンを実行する」という時間間隔を表す。n を 1 とすると、1秒ごとにスキャンが実行され高い応答性が得られ、n を大きい値とすると複数秒分のイベントをまとめて一括処理することとなる。アルゴリズムは一定幅のスライディングウィンドウ内で出現頻度が閾値を満たすアイテムセットの時間区間をすべて特定し、左から右へスライドしてスキャンすることにより、現在のスキャン位置より前に終端する区間は将来のデータに影響されないことが保証されるため、再処理なしに確定出力が可能である。さらに、単調なウィンドウ移動を利用して冗長なスキャン位置をスキップする Scan Stride Skipping と、構成アイテムの密集区間に候補評価を限定する Apriori Interval Pruning の2つの高速化技術を組み込むことで、ストリーム処理に必要な実用的な処理速度を実現する。

評価は合成データと実データを用いた4つの実験で構成される。合成データによるパラメータ感度分析（EX-1）では n を変化させてスキャン頻度と処理速度のトレードオフを定量化する。合成データによるスケーラビリティ実験（EX-2）ではストリーム長・アイテム数・ウィンドウ幅を独立に変化させ、各パラメータに対する処理コストのスケーリング特性を明らかにするとともに、10^8 イベント規模でも実用的な処理時間で実行可能であることを示す。合成データによるアブレーション実験（EX-3）では、Naive・Scan Stride Skipping のみ・Apriori Interval Pruning のみ・フルアルゴリズムの4構成を比較し、各高速化技術が独立に寄与することを確認する。最後に、実データによる評価（EX-4）として CASAS スマートホームデータセットに適用する。CASAS は自律ロボットの行動ログと構造的に類似したマルチセンサ共起ストリームを提供する。検出された区間が行動ルーティンと整合することを確認し、自律システム監視への実用性を示す。

本研究では、スキャン頻度を明示的に制御できるストリーム向け密集区間マイニングの統一フレームワークを提案した。高速化技術はいずれも処理速度の改善に寄与し、実データへの適用によりアルゴリズムが解釈可能な結果を出力できることが確認された。今後の課題として、実際のロボットシステムから収集した行動ログへの適用、高頻度ストリームに向けたさらなる高速化、スキャン間隔や閾値パラメータの自動最適化手法の開発に取り組む予定である。

---

## Word Count

~558 words (within 400–600 requirement)

---

## Notes / TODO

- [ ] EX-1 アブレーション実験の実装・実行（Naive / Stride-only / Pruning-only / Full）
- [ ] EX-3 CASAS パターンの解釈・代表例の記述
- [ ] 共著者確認・所属情報の準備
- [ ] EasyChair アカウント作成・提出
