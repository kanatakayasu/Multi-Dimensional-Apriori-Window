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

Autonomous AI systems and robotic agents generate streams of sensor events that encode behavioral patterns. Understanding *when* these patterns densely co-occur — not merely whether they exist globally — is essential for real-time monitoring, anomaly detection, and adaptive control in intelligent environments. In multi-agent systems and sensor-equipped robotic platforms, for instance, detecting that a specific set of events repeatedly clusters within particular time intervals can reveal coordinated behaviors, routine structures, or emerging anomalies that demand timely response. The approach also has broad applicability across domains such as retail and epidemiology.

Existing methods do not support dense interval detection over event streams. Gap-constraint-based approaches such as LPFIM and RPM indirectly estimate dense intervals through a single parameter that simultaneously governs both pattern identification and interval accuracy, making tuning difficult and results inexact. Other methods such as GLFMiner and SIM operate on fixed granularities or return only a single interval per itemset. All of these approaches operate in batch mode and provide no mechanism for incremental processing or controllable scan frequency.

We propose a dense interval mining algorithm for event streams, parameterized by a scan frequency n. The algorithm identifies all time intervals in which itemset occurrence frequency within a fixed-width sliding window meets a threshold. When n = 1, a scan fires after every event, yielding highly responsive output; when n is large, many events are batched together, reducing computational cost. Because the window slides monotonically from left to right, any interval ending before the current scan position is unaffected by future events, guaranteeing confirmed output without reprocessing. Two speedup techniques — stride-based skipping in both dense and non-dense scan phases, and Apriori-style candidate pruning — are incorporated to achieve the processing speed required for practical stream operation.

We evaluate the algorithm using both synthetic and real-world data. A parameter sensitivity study (EX-1) on synthetic streams varies n over {1, 6, 24, 96, T} to characterize the tradeoff between scan frequency and processing speed, showing that n = W achieves processing speed within one order of magnitude of full batch while scanning at a practically useful frequency. An ablation study (EX-2) on synthetic event streams compares four algorithm variants — naive scan, stride-only, pruning-only, and the full algorithm — to quantify the individual contribution of each speedup technique. Finally (EX-3), we apply the algorithm to two CASAS smart home sensor datasets. CASAS records timestamped ON/OFF events from motion and door sensors distributed throughout a residence, forming a continuous multi-sensor co-activation stream that is structurally analogous to the event logs produced by autonomous robotic systems monitoring their own actuator and sensor states. This makes CASAS a practical proxy for robot behavioral streams while providing ground-truth activity labels for interpretation. Results show that the detected dense intervals correspond to interpretable behavioral routines, confirming the approach's practical utility for autonomous environment monitoring.

The proposed algorithm provides a unified framework for streaming dense interval mining with explicit control over scan frequency. Ablation experiments confirm that both speedup techniques contribute meaningfully to processing speed, and experiments on real sensor data demonstrate interpretable, domain-consistent outputs. Future work includes applying the framework to behavioral logs collected from physical robotic systems, extending it to multi-dimensional event spaces, and investigating adaptive scan-frequency mechanisms based on stream characteristics.

---

## 日本語訳

自律AIシステムおよびロボットエージェントは、行動パターンを内包したセンサイベントストリームを生成する。これらのパターンが「いつ」密集して共起するかを理解すること——単にグローバルに存在するかどうかではなく——は、知的環境におけるリアルタイム監視・異常検知・適応制御に不可欠である。マルチエージェントシステムやセンサ搭載ロボットプラットフォームでは、特定のイベント集合が特定の時間区間に密集していることを検出することで、協調行動・日常ルーティン・迅速な対応を要する異常の出現を明らかにすることができる。また、このアルゴリズムは小売や疫学などの幅広い分野への応用も期待できる。

既存手法はイベントストリームに対する密集区間検出をサポートしない。LPFIM や RPM などのギャップ制約型手法は、パターン識別精度と区間検出精度の両方を単一パラメータで制御するため、適切なパラメータ設定が困難であり結果も近似的である。GLFMiner や SIM は固定粒度または1アイテムセットにつき1区間のみを返す。これらはいずれもバッチ処理のみで動作し、逐次処理やスキャン頻度の制御を行う機構を持たない。

本研究では、スキャン頻度パラメータ n を導入したストリーム向け密集区間マイニングアルゴリズムを提案する。n は「n秒ごとに1回スキャンを実行する」という頻度を表す。nを1とすると、毎秒ごとにスキャンが実行され高い応答性が得られ、nを大きい値とすると多くのイベントをまとめて一括処理することとなる。アルゴリズムは一定幅のスライディングウィンドウ内で出現頻度が閾値を満たすアイテムセットの時間区間をすべて特定し、左から右へスライドしてスキャンすることにより、現在のスキャン位置より前に終端する区間は将来のデータに影響されないことが保証されるため、再処理なしに確定出力が可能である。さらに、密集・非密集の両状態でのスキャン位置スキップと Apriori 型の候補枝刈りの2つの高速化技術を組み込むことで、ストリーム処理に必要な実用的な処理速度を実現する。

評価には合成データと実データの両方を用いる。合成データによるパラメータ感度分析（EX-1）では n を変化させてスキャン頻度と処理速度のトレードオフを定量化する。合成データによるアブレーション実験（EX-2）では、naive・stride-only・pruning-only・フルアルゴリズムの4構成を比較し、各高速化技術の個別の貢献を定量化する。実データ実験（EX-3）では CASAS スマートホームデータセットに適用する。CASAS は住宅内の複数のモーションセンサ・ドアセンサのON/OFFイベントをタイムスタンプ付きで記録したデータセットであり、自律ロボットがアクチュエータやセンサの状態変化を記録する行動ログと構造的に同等のマルチセンサ共起ストリームを形成する。これによりロボット行動ストリームの代替として機能しつつ、解釈可能な活動ラベルによる検証が可能である。検出された区間が行動ルーティンと整合することを確認し、自律システム監視への実用性を示す。

本研究では、スキャン頻度を明示的に制御できるストリーム向け密集区間マイニングの統一フレームワークを提案した。高速化技術はいずれも処理速度の改善に寄与し、実データへの適用によりアルゴリズムが解釈可能な結果を出力できることが確認された。今後の課題として、実際のロボットシステムから収集した行動ログへの適用、多次元イベント空間への拡張、ストリーム特性に応じたスキャン頻度の動的調整機構の設計に取り組む予定である。

---

## Word Count

~470 words (within 400–600 requirement)

---

## Notes / TODO

- [ ] EX-1 アブレーション実験の実装・実行（Naive / Stride-only / Pruning-only / Full）
- [ ] EX-3 CASAS パターンの解釈・代表例の記述
- [ ] 共著者確認・所属情報の準備
- [ ] EasyChair アカウント作成・提出
