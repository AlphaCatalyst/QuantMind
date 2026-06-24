# QuantGPT 因子挖掘整合方案

## 定位

QuantMind 对外暴露的是独立的“因子研究”能力；QuantGPT 在其中定位为当前可接入的因子研究与因子进化引擎，不替代 QuantMind 的训练、模型注册、推理、回测和交易执行主链路。

目标是把 QuantGPT 的表达式解析、因子分组回测、反过拟合验证、滚动验证、因子评分和进化搜索能力，收敛到 QuantMind 的投研、训练、信号和风控体系内。

当前状态：

- 已落地：`backend/services/engine/research/` 中的 QuantGPT adapter、payload mapping、promotion gate、signal adapter。
- 已落地：底部导航 `因子研究` 入口，路由为 `/factor-research`，位置在 `模型训练` 之前；前端工作台为 `electron/src/features/research/components/FactorResearchWorkbench.tsx`，会在最新 completed run 后展示 factor values 总量、覆盖日期数、股票数和样本值。
- 已落地：候选因子与评估 run 的基础持久化闭环，API 为 `/api/v1/research/factors/*`。
- 已落地：本地同步 evaluator 与 `qm_factor_values` 因子值落库；当前支持白名单模板表达式，缺少本地行情表时会把 run/candidate 明确置为失败/阻断状态。`GET /api/v1/research/factors/runs/{run_id}/values` 已提供分页抽样、覆盖日期数、symbol 数、factor value 范围、空值数、异常股票代码样本、source 分布和近期日期分布，供训练、信号和投研联调核对。
- 已落地：Campaign 基础闭环，已生成 `qm_factor_campaigns` 和 `qm_factor_campaign_items`；当前默认采用 QuantMind 本地安全 `mutation_crossover`，也可显式切换为兼容模式 `template_mutation`。`mutation_crossover` 会对白名单表达式做窗口突变，并通过 hybrid 表达式交叉组合均线相对价格与动量信号，逐个复用 candidate/run/evaluator，并支持 bounded 多代 generation，下一代从上一代最高分表达式继续进化。已补资源配额门禁，默认单次最多 20 个候选、每用户最多 1 个活动 campaign、每日最多 100 个候选；`run_async=true` 可创建 pending campaign 并由后台执行入口回写 completed/failed，`claim_next_pending_factor_campaign()` 使用 `FOR UPDATE SKIP LOCKED` 原子领取 pending campaign，`factor_campaign_worker.py --once` 可独立处理一条待执行任务；worker 每轮会先将超时 running campaign 重新置为 pending，避免进程异常后长期占用 active 配额；前端默认异步启动并复用轮询刷新结果；active campaign 可通过取消 API 和前端按钮显式终止，前端可在 Campaign 历史中选择任一 campaign 查看 generation summary 和候选明细，并可将当前选中 campaign best candidate 直接晋升为 Shadow Feature。
- 已落地：Feature promotion 基础闭环，已生成 `qm_factor_feature_promotions` 和 shadow feature set version；未物化到训练快照的因子保持 `pending_materialization`，不会进入 active training catalog；已有训练快照时可将 factor values 原子 merge 到 `model_features_YYYY.parquet`，缺年份快照时可用本地 OHLCV 生成 baseline snapshot，成功后激活 feature set。
- 已落地：训练桥接闭环，已生成 `qm_factor_training_runs`；物化后的 promotion 可显式调用现有模型训练提交链路，记录 factor promotion 到 training run 的关联，并从 `admin_training_jobs` 同步 `status/progress/result`。
- 已落地：自动 baseline 训练对比基础闭环；提交训练时可携带 `baseline_metrics` 或 `baseline_training_run_id`，未携带时后端默认先提交去掉 promoted factor 的 baseline 训练，再提交 promoted shadow 训练，结果回流后生成 promoted vs baseline 的 AUC/RMSE 对比和训练门禁建议。
- 已落地：训练门禁审批桥接；completed 且门禁允许的因子训练候选，普通用户先通过 `POST /api/v1/research/factors/trainings/{training_id}/approval-requests` 提交默认模型审批请求，管理员或拥有 `factor.approve` 的审批人通过 `POST /api/v1/research/factors/approval-requests/{request_id}/review` 审核，也可直接调用 `POST /api/v1/research/factors/trainings/{training_id}/approve` 设置默认模型。审批记录会回写 `qm_factor_training_runs.metadata_json` 并追加到 `qm_factor_approval_audit`。审计记录可通过 `GET /api/v1/research/factors/approvals` 查询，审批请求可通过 `GET /api/v1/research/factors/approval-requests` 查询，审批策略可通过 `GET/PUT /api/v1/research/factors/approval-policy` 按 tenant 配置直接审批、自审和最少审批人数。前端 Feature 晋升面板展示最近审批审计、最近审批请求和审批策略，并为有审批权限的用户提供策略配置和通过/拒绝请求操作。
- 已落地：因子研究训练注册模型时会把 `factor_research` 上下文写入模型元数据，包括 promoted factor key、表达式、feature set version 和 baseline run；模型管理归因分析页会展示该来源上下文，并与 SHAP 贡献榜同屏查看。
- 已落地：Shadow Signal 基础闭环，已生成 `qm_factor_signal_runs`、`engine_feature_runs`、`engine_signal_scores`；`publish_stream` 默认关闭，只写 shadow 产物表，写 Redis stream/latest 时必须显式 `allow_shadow_stream=true`；trade runner 和自动托管执行读库侧默认拒绝 `factor_shadow`，必须显式 `allow_factor_shadow_signals=true` 才允许消费。
- 已落地：基础运行健康摘要，`GET /api/v1/research/factors/health` 汇总 candidate/run/promotion/campaign/training/signal/approval 状态、失败/待物化/活跃 campaign/worker event/配额指标、SLO 指标和告警；SLO 覆盖 run/campaign 成功率、campaign P95 耗时、pending/stale campaign 和 backfill failed jobs；`GET /api/v1/research/factors/campaign-worker-events` 可查询最近 worker 事件；每日 campaign 候选预算按 `n_candidates * max_generations` 统计，并在接近/打满预算时产生 warning/critical 告警；`/metrics` 暴露因子研究 health status、alert count、indicator 和 quota policy gauge；前端因子研究工作台展示运行健康与 SLO 面板，Playwright 主流程覆盖该面板。
- 已落地：adapter 单元测试和真实数据只读 smoke 脚本。
- 已落地：受 QuantMind evaluator 白名单保护的 QuantGPT evolution adapter；新增 `quantgpt_meta_evolution` 和 `quantgpt_crossover_only` campaign strategy，adapter 会本地加载 QuantGPT `meta_evolution/trajectory_analyzer/mutation_engine` 做策略选择和诊断，候选输出必须先通过 `quantgpt_expression_guard`，确保不会触发外部提交，也不会把当前 evaluator 无法执行的表达式写入 campaign。
- 已落地：本地表达式执行器扩展到 QuantGPT 常见白名单算子，除价格均值偏离、动量和 hybrid 外，已支持 `rank(volume / ts_mean(volume, W))`、`rank(amount / ts_mean(amount, W))`、`rank(vwap / ts_mean(vwap, W))`、`rank(ts_std(close, W))`、`rank(ts_corr(rank(close), rank(volume), W))`、`rank(tanh(ts_delta(close, W) / ts_shift(close, W)))`、`rank(ts_rank(close, W))`、`rank(decay_linear(close, W))`、`rank(zscore(close, W))`、`rank(scale(volume))` 和固定模板 `rank(where(close > ts_mean(close, W), close / ts_mean(close, W), 0))`；SQL path、feature snapshot/Qlib pandas path、evolution adapter 和 evolution guard 共用同一支持范围。
- 未完成：完整 QuantGPT 任意表达式 AST 执行器、通知型监控告警管道、告警静默/升级和大规模容量压测；这些属于主链路完成后的 post-MVP 增强，不阻断 QuantMind 内部因子挖掘闭环。

## QuantGPT 能力映射

| QuantGPT 能力 | QuantMind 落点 | 说明 |
| --- | --- | --- |
| 表达式解析 | factor evaluation task | 负责校验和计算候选表达式 |
| 分组回测 | factor evaluation run | 生成 Rank IC、IC IR、turnover、monotonicity 等指标 |
| anti-overfit | promotion gate | 作为候选因子晋升前置条件 |
| rolling validation | historical replay | 判断样本外衰减和方向稳定性 |
| factor score | candidate score | 统一落到候选因子评分 |
| factor values | factor value store / signal adapter | 可转 feature，也可转 shadow signal |
| mutation/crossover | factor mining campaign | 自动生成下一批候选表达式 |
| WQ BRAIN | 默认关闭 | 不进入 QuantMind 生产链路，避免外部提交风险 |

## 总体架构

```text
QuantMind Web / AI-IDE / 因子研究
  -> quantmind-api /api/v1/research/factors/*
  -> quantmind-engine research service
  -> QuantGPT sidecar or embedded runner
  -> QuantMind local data adapter
  -> qm_factor_candidates / qm_factor_candidate_runs / qm_factor_values
  -> feature catalog promotion
  -> model training / model registry / inference
  -> shadow signal publication / backtest / simulation trading
```

## 端到端 Pipeline

因子研究是模型训练的上游，不应作为投研平台或模型训练页内部的附属 tab。完整流水线应固定为：

1. 因子构思：手动表达式、模板库、AI 生成、QuantGPT campaign seed。
2. 数据准备：股票池、时间窗口、OHLCV、feature snapshot，全部使用 QuantMind 数据口径。
3. 计算评估：生成 factor values、分组收益、Rank IC、IC IR、turnover、monotonicity。
4. 研究门禁：反过拟合、滚动验证、覆盖率、方向稳定性、成本敏感性。
5. 入库版本：写入 candidate、run、factor values，形成可追溯 Factor Catalog。
6. 晋升训练：通过门禁的因子生成 shadow feature set，进入模型训练的特征选择。
7. 灰度信号：可选转为 shadow signal，供回测中心、模拟盘和 shadow runner 消费。
8. 监控回滚：跟踪线上/离线衰减，支持版本回退、审计和权限审批。

模型训练页的“特征选择”只消费已存在或已晋升的 feature；它不负责发现、验证和进化因子。

### 部署边界

建议第一阶段以 sidecar 方式运行 QuantGPT：

- QuantGPT 使用内部端口 `8013`，避免和 QuantMind `stream:8003` 冲突。
- 默认配置 `QUANTGPT_ENABLED=false`，显式打开后才暴露功能。
- QuantGPT 不直接访问外部生产数据库；生产数据从 QuantMind 本地库或 feature snapshot 注入。
- WQ BRAIN、Cloud submit、外部自动提交能力默认禁用；QuantMind 侧通过 `backend/services/engine/research/external_submit_guard.py` 强制执行，`QUANTMIND_FACTOR_RESEARCH_ALLOW_EXTERNAL_SUBMIT` 未显式为 true 时，即使环境中存在 WQ BRAIN 凭证也不允许外部提交。

后续如果依赖和运行时稳定，再考虑把 QuantGPT 的表达式引擎与验证模块内嵌为 engine 子模块。

## 数据口径

### 输入数据源

生产顺序：

1. QuantMind 本地 PostgreSQL：`stock_daily_latest`。
2. QuantMind feature snapshot Parquet。
3. QuantMind Qlib 数据。
4. QuantGPT 自带缓存只允许 research 对照，不作为生产验收依据。

当前本地 evaluator 默认读取 `stock_daily_latest`，可通过 `FACTOR_RESEARCH_DATA_TABLE` 覆盖表名。若该表缺失，会先从 `TRAINING_LOCAL_DATA_PATH/model_features_*.parquet` 读取已有训练快照中的 `trade_date/symbol/open/high/low/close/volume`，再从 `FACTOR_RESEARCH_QLIB_PROVIDER_URI` / `QLIB_PROVIDER_URI` / `db/qlib_data` 指向的 Qlib provider 读取 `$open/$high/$low/$close/$volume` 作为兜底输入，并复用同一白名单表达式、Rank IC 统计、promotion gate 和 `qm_factor_values` 入库 contract。Qlib provider 也已能生成完整 QuantGPT runner `market_df` 输入：`trade_date/stock_code/open/high/low/close/volume/amount/pct_change`，其中 `stock_code` 转为 QuantGPT/baostock 风格 `sh.600000` / `sz.000001`，`amount` 和 `pct_change` 从 QuantMind OHLCV 派生。表、快照和 Qlib provider 都不可用、表达式不在白名单、或没有生成任何截面值时，run 必须进入 `failed`，candidate 必须进入 `rejected`，前端展示阻断原因。

Feature promotion 不直接假设训练数据已就绪。promotion 会检查 `TRAINING_LOCAL_DATA_PATH` 下的 `model_features_*.parquet` 是否存在同名 feature 列：

- 已存在：生成 active feature set，模型训练页可消费。
- 未存在：生成 shadow feature set，promotion 状态为 `pending_materialization`，前端提示需要先物化训练快照。

物化接口按 `trade_date + symbol` 处理 factor values：

- 目标 `model_features_YYYY.parquet` 已存在时，按现有训练快照行 merge 新 feature 列，并使用临时文件原子替换目标 parquet。
- 目标年份快照不存在时，按 factor values 的 `(trade_date, symbol)` 先从本地 `FACTOR_RESEARCH_DATA_TABLE`（默认 `stock_daily_latest`）只读 OHLCV；若本地行情缺失，再从 `FACTOR_RESEARCH_QLIB_PROVIDER_URI` / `QLIB_PROVIDER_URI` / `db/qlib_data` 指向的 Qlib provider 读取同一批标的日期的 `$open/$high/$low/$close/$volume`，生成包含 `trade_date/symbol/open/high/low/close/volume/<feature>` 的 baseline `model_features_YYYY.parquet`。
- 查询本地行情时使用 `SH600000` 前缀格式匹配；写入训练 snapshot 时沿用训练脚本已有的 6 位 `symbol` 口径。
- 本地行情表、Qlib provider、行情行、OHLCV 不完整或没有匹配行时，promotion 继续保持 `pending_materialization`，不会创建伪造训练样本。

### 股票代码

所有入库、API 返回、signal 发布必须使用 QuantMind 前缀格式：

- 正确：`SH600519`、`SZ000001`
- 禁止：`600519.SH`、`sh.600519`

适配层统一使用：

- `backend/shared/stock_utils.py::StockCodeUtil.to_prefix`
- `backend/services/engine/research/quantgpt_mapping.py::normalize_quantgpt_symbol`

### Factor Value Schema

QuantGPT 输出进入 QuantMind 前必须标准化为：

```text
tenant_id
user_id
candidate_id
run_id
trade_date
symbol
factor_value
source
created_at
```

QuantGPT adapter 当前兼容两类外部 factor value contract，并统一收敛为上述行格式：

- `/api/v1/factor_values` 返回的 `data[].values` date-grouped payload。
- `/api/v1/tasks/{task_id}` completed result 中的 `stock_factor_data.stocks` payload，使用 `rebalance_date` 作为 `trade_date`，读取 `stock_code` 和 `factor_value`。

非法 symbol 会被计入 `invalid_symbol_count` 并跳过，不会进入 QuantMind 入库、训练快照或 shadow signal 链路。相关回归测试为 `test_parse_factor_values_payload_accepts_task_stock_factor_data_contract`。

## 后端设计

### 模块结构

已存在：

- `backend/services/engine/research/quantgpt_client.py`
- `backend/services/engine/research/quantgpt_mapping.py`
- `backend/services/engine/research/factor_promotion.py`
- `backend/services/engine/research/factor_signal_adapter.py`
- `backend/services/engine/research/schemas.py`
- `backend/services/api/routers/research_factor_service.py`

需要补齐：

- `backend/services/engine/research/factor_candidate_evaluator.py`：把当前 API service 内的同步 evaluator 下沉为可异步调度的 engine service。
- `backend/services/engine/research/factor_campaign_service.py`
- `backend/services/engine/research/factor_value_store.py`
- `backend/services/engine/tasks/quantgpt_factor_tasks.py`

### 数据表

建议新增表：

```text
qm_factor_candidates
qm_factor_candidate_runs
qm_factor_values
qm_factor_feature_promotions
qm_factor_signal_runs
qm_factor_campaigns
```

已落地：

- `qm_factor_candidates`
- `qm_factor_candidate_runs`
- `qm_factor_values`
- `qm_factor_feature_promotions`
- `qm_factor_signal_runs`
- `qm_factor_campaigns`
- `qm_factor_campaign_items`
- `qm_factor_training_runs`
- `engine_feature_runs`
- `engine_signal_scores`

核心字段：

`qm_factor_candidates`

- `id`
- `tenant_id`
- `user_id`
- `expression`
- `expression_hash`
- `name`
- `description`
- `source`
- `status`: `draft/evaluating/validated/rejected/promoted/archived`
- `created_at`
- `updated_at`

`qm_factor_candidate_runs`

- `id`
- `candidate_id`
- `tenant_id`
- `user_id`
- `quantgpt_task_id`
- `status`
- `universe`
- `start_date`
- `end_date`
- `rank_ic_mean`
- `ic_ir`
- `turnover`
- `wq_fitness`
- `monotonicity_score`
- `anti_overfit_score`
- `coverage_days`
- `invalid_symbol_count`
- `raw_payload`
- `created_at`
- `updated_at`

`qm_factor_values`

- `candidate_id`
- `run_id`
- `tenant_id`
- `user_id`
- `trade_date`
- `symbol`
- `factor_value`
- `source`
- `created_at`

只读查询接口：

- `GET /api/v1/research/factors/runs/{run_id}/values?limit=100&offset=0`
- 先校验 run 属于当前 tenant/user，再返回 `run`、`summary`、`items` 和 `pagination`。
- `summary` 包含 total、tradeDateCount、symbolCount、min/max trade date、min/max factor value。
- `items` 使用 `tradeDate/symbol/factorValue/source/createdAt` contract，供前端、训练桥接、Shadow Signal 和排障脚本抽样核对。

建议按 `trade_date` 和 `candidate_id` 建索引；全 A 长窗口场景下再考虑分区。

`qm_factor_feature_promotions`

- `candidate_id`
- `run_id`
- `tenant_id`
- `user_id`
- `feature_key`
- `feature_id`
- `version_id`
- `status`
- `materialization_status`
- `metadata_json`
- `created_at`
- `updated_at`

### API

建议由 `quantmind-api` 代理到 `quantmind-engine`，用户态统一走 `/api/v1`。

```text
POST /api/v1/research/factors/candidates
GET  /api/v1/research/factors/candidates
GET  /api/v1/research/factors/candidates/{candidate_id}
POST /api/v1/research/factors/candidates/{candidate_id}/evaluate
GET  /api/v1/research/factors/runs/{run_id}
GET  /api/v1/research/factors/promotions
POST /api/v1/research/factors/candidates/{candidate_id}/compute-values
POST /api/v1/research/factors/candidates/{candidate_id}/promote
POST /api/v1/research/factors/promotions/{promotion_id}/materialize
GET  /api/v1/research/factors/signals
POST /api/v1/research/factors/candidates/{candidate_id}/publish-shadow-signal
POST /api/v1/research/factors/campaigns
GET  /api/v1/research/factors/campaigns
GET  /api/v1/research/factors/campaigns/{campaign_id}
GET  /api/v1/research/factors/trainings
POST /api/v1/research/factors/promotions/{promotion_id}/train
```

所有写接口必须带：

- `tenant_id`
- authenticated `user_id`
- request id / trace id
- feature flag check

### 异步任务

因子评估、全量 factor values、历史回放、promotion 训练都应异步执行。

当前开发版为了形成可点击闭环，`POST /api/v1/research/factors/candidates/{candidate_id}/evaluate` 默认同步调用本地 evaluator；如需只创建任务，可设置 `FACTOR_RESEARCH_SYNC_EVAL=false`。

任务状态：

```text
pending -> running -> completed
pending -> running -> failed
pending -> cancelled
```

失败必须保存：

- `failure_stage`
- `error_code`
- `error_message`
- `raw_payload`

## 两条闭环路径

### A. 因子晋升为训练特征

这是主路径。

流程：

1. 用户或 campaign 产生候选表达式。
2. 本地 evaluator 或 QuantGPT runner 执行表达式校验、因子值计算、分组回测、反过拟合、滚动验证。
3. QuantMind 保存候选因子和 run 指标。
4. promotion gate 检查是否达标。
5. 通过后生成 feature definition。
6. 生成 shadow feature set version。
7. 检查训练快照是否已物化同名 feature 列；未物化时保持 `pending_materialization`，禁止进入 active catalog。
8. 回填/物化历史 factor values 到已有训练特征快照。
9. 物化完成后切换 active feature set version；训练页通过 `/api/v1/models/feature-catalog` 读取到该 feature。
10. 调用现有 `/api/v1/models/run-training`。
11. 注册新模型。
12. 和 baseline 模型同窗口对比。
13. 人工或规则审批后设为默认模型或绑定策略。

数据 contract：

- 因子研究生产路径只使用 QuantMind 本地 PostgreSQL 数据源，不调用 QuantGPT 外部抓数。
- `stock_daily_latest` 通过 local market data adapter 输出固定 OHLCV schema：`trade_date/symbol/open/high/low/close/volume`。
- `symbol` 在 adapter 层统一为 `SH600000` / `SZ000001` / `BJ430001` 前缀格式；后缀格式只作为输入兼容，不进入下游产物。
- 本地 evaluator 当前复用该 adapter 生成 factor values；完整 QuantGPT runner input 会从同一 OHLCV contract 转换为 QuantGPT `market_df`，补齐 `stock_code/amount/pct_change`，避免两套数据口径。

晋升阈值建议：

- `abs(rank_ic_mean) >= 0.015`
- `ic_ir >= 0.15`
- `turnover <= 0.35`
- `monotonicity_score >= 0.6`
- `anti_overfit_score >= 60`
- `coverage_days >= 120`
- 与现有正式特征最大相关性 `<= 0.85`

### B. 因子转 shadow signal

这是快速灰度路径，不等同模型上线。

流程：

1. 计算某日截面 factor values。
2. 做 rank/z-score 标准化。
3. Top N 生成 BUY signal。
4. long-short 模式下 Bottom N 生成 SELL/short signal。
5. 写入 `engine_signal_scores`。
6. 发布 `qm:signal:stream:{tenant}`。
7. 更新 `qm:signal:latest:{tenant}:{user}`。
8. 模拟盘或 shadow runner 消费。

限制：

- 初期只允许 simulation/shadow。
- 实盘前必须通过现有风控、停牌过滤、涨跌停过滤、重复订单保护。
- runner 只消费 latest run，旧 run 必须丢弃。

## 自动因子挖掘 Campaign

QuantGPT 的 mutation/crossover/evolution 能力应在 QuantMind 中表现为 campaign。

Campaign 输入：

- seed expressions
- universe
- date range
- max generations
- population size
- mutation budget
- validation profile
- promotion policy

Campaign 输出：

- candidate list
- 每代 score 分布
- 被淘汰原因
- 最终候选
- 可晋升候选
- quota policy / usage：每次 campaign metadata 记录单次候选上限、活动 campaign 上限、每日候选预算、当前已用量和本次请求量。

默认资源门禁：

- `QUANTMIND_FACTOR_CAMPAIGN_MAX_CANDIDATES=20`
- `QUANTMIND_FACTOR_CAMPAIGN_MAX_ACTIVE_PER_USER=1`
- `QUANTMIND_FACTOR_CAMPAIGN_DAILY_CANDIDATE_BUDGET=100`
- 超过单次候选数、已有 running/pending campaign、或超过每日候选预算时，创建 API 返回明确错误，不写入新的 campaign。

建议阶段：

1. 手动表达式评估。
2. 批量 seed expression 评估。
3. mutation-only campaign。
4. mutation + crossover campaign。
5. 自动触发 promotion shadow training。

## 前端整合

现有入口：

- 底部导航 `因子研究`。
- 导航顺序必须在 `模型训练` 之前，表达“因子研究 -> 模型训练 -> 模型管理”的上游关系。
- 路由：`/factor-research`。
- 页面：`electron/src/pages/FactorResearchPage.tsx`。
- 工作台组件：`electron/src/features/research/components/FactorResearchWorkbench.tsx`。
- 工作台默认进入 `挖掘` 模式，优先暴露自动因子 Campaign；手动评估、晋升和信号发布作为同一工作台内的正交操作保留。
- 投研平台保留为候选池、自选、研究池工作台，不承载因子挖掘任务。
- 候选队列展示 candidate/run 状态、失败原因、Rank IC、覆盖天数和因子值条数。
- 门禁表读取最新 run 的指标与 gate decision，完成/失败/阻断状态不再只用静态占位文案。
- Feature 晋升面板展示 `feature_key`、shadow feature set version 和物化状态；未物化时提示不能进入模型训练 active catalog。
- Feature 晋升面板可触发物化到训练快照；如果快照缺失或无匹配行，会保留 pending 状态并显示原因。
- Feature 晋升面板可在 `materialized` 后显式发起 Shadow 训练；后端复用现有 `/models/run-training` 提交链路，并保存 `qm_factor_training_runs` 关联。
- Feature 晋升面板发起训练时默认请求自动 baseline；后端先提交同窗口、去掉 promoted factor 的 baseline 训练，再提交 promoted shadow 训练，并自动把 baseline run id 写入 promoted payload。
- Feature 晋升面板展示最新训练的 `training_run_id`、训练状态、进度和结果摘要；刷新时后端从 `admin_training_jobs` 回流训练任务快照。
- Feature 晋升面板展示 promoted vs baseline 对比摘要；没有 baseline 时明确显示待补 baseline。
- Feature 晋升面板展示训练门禁建议：待审批晋升、继续观察、建议回滚或证据不足；当训练 completed、门禁允许且训练结果含 ready 注册模型 id 时，普通用户可点击 `提交审批请求` 进入待审核队列，管理员或拥有 `factor.approve` 的审批人可点击 `审批为默认模型`。同一 training/model 重试审批时，如果模型管理当前默认模型仍一致，后端幂等返回已有审批，不重复设置默认模型、不刷新原审批时间，但会追加一条 `idempotent_replay` 审计记录。
- 审批请求会写入 `qm_factor_approval_requests`，同一 tenant/user/training 只允许一个 pending 请求；管理员或拥有 `factor.approve` 的审批人查询接口可看 tenant 内请求，普通用户只能看自己的请求。前端通过 `/api/v1/rbac/check-permission?permission_code=factor.approve` 判断是否展示 `通过请求` / `拒绝请求` 操作。审核通过时以后端 reviewer 身份写入审批元数据，审核拒绝会保留 rejected 决策记录但不触发默认模型切换。
- 审批策略会写入 `qm_factor_approval_policies`，默认兼容历史行为：允许直接审批、允许自审、最少 1 人审批。组织可关闭直接审批，要求所有默认模型晋升先进入审批请求；也可关闭自审或提高 `min_approvals`。创建审批请求时会保存策略快照，审核时按该快照累计审批人并阻止重复审核。
- 默认模型审批会写入独立审计表 `qm_factor_approval_audit`，记录 training、factor run、promotion、candidate、model、gate、request metadata、default model snapshot、正常审批/幂等重放状态；查询接口为 `GET /api/v1/research/factors/approvals`。
- 审批成功后，前端明确提示“自动托管只消费默认模型生产批次”，并提供跳转模型管理生成生产批次的入口；设置默认模型不等价于已经产生可交易推理批次。
- Feature 晋升面板展示最近审批审计，便于确认审批状态、模型 id、原因和幂等重试。
- Feature 晋升面板支持软回滚；回滚后 promotion 标记为 `rolled_back`，并激活一个移除该 factor 的 feature set，不删除历史 candidate/run/factor values。
- 运维回滚工具已落地：`backend/services/engine/scripts/factor_research_rollback_tool.py` 默认 dry-run，只检查健康状态、认证、promotion 归属和将受影响的 feature/version；传 `--execute` 后才调用回滚 API，并校验返回的 `status/materializationStatus` 都为 `rolled_back`。可通过 `--promotion-id` 指定目标，也可用 `--latest-active` 选择当前用户最近的 active/materialized promotion。
- 活动中的 campaign/training run 会每 5 秒自动刷新；完成、失败或回滚后停止轮询。Campaign 启动默认使用 `run_async=true`，创建后先返回 pending/running 状态，工作台依靠轮询读取 detail 中的 generation summary 和候选明细。
- Campaign 面板展示当前选中 campaign、完成候选数、代际进度、generation summary、最佳表达式、Campaign 历史和候选历史；候选历史会显示 `run_id`、`candidate_id`、RankIC/ICIR/Turnover、失败或淘汰原因、进化算子、parent expressions 和 evolution reason，作为 campaign 排障和复现实验入口。启动动作复用当前表达式、股票池和评估窗口，可设置策略和 bounded `max_generations`，并默认异步提交；策略包括默认 `mutation_crossover`、`quantgpt_meta_evolution`、`quantgpt_crossover_only` 和兼容 `template_mutation`。`mutation_crossover` 会生成可被 SQL、训练快照和 Qlib 兜底 evaluator 共同计算的 hybrid 表达式；best candidate 可直接触发 Shadow Feature 晋升，metadata 保留 `campaign_id` 和 `source=campaign_best_candidate`。
- Campaign 创建已接入资源配额门禁；配额失败会在创建前阻断，不产生半成品 campaign。单元测试覆盖默认配额、单次候选超限、bounded 多代候选计数、活动 campaign 超限和每日候选预算超限。
- Campaign 配额测试已覆盖边界允许场景：单次候选数或每日候选预算刚好到上限时允许通过，并返回 quota usage 审计快照。
- Shadow Signal 面板展示 latest signal run、信号数量和 Redis stream 写入状态；发布动作默认只写 shadow signal 表，不写 Redis；写 stream 需要服务端二次确认 `allow_shadow_stream=true`。
- 运行健康面板展示最近 24 小时失败 run、待物化特征、活跃 campaign 和告警摘要；告警包括长时间未完成 run、近期失败 run、stale running campaign、待物化特征、campaign 活动配额占满、每日候选预算接近/打满和 shadow signal 写入实时流。
- 最新评估状态面板在 completed run 后读取 `GET /api/v1/research/factors/runs/{run_id}/values`，展示 factor values 预览和质量摘要，包含空值数、异常股票代码数、source 分布和样本值，作为训练/信号消费前的前端产物核对。
- Playwright 已覆盖 mock API 前端主路径：创建/轮询 evaluation run、启动 bounded Campaign 并校验 `max_generations` payload 与 generation summary 展示、completed run 的 factor values 预览、已物化 promotion 发起 Shadow 训练并校验 `auto_baseline` payload、训练门禁通过后审批为默认模型、审批后连续跳转模型训练验证 `factor_research` feature catalog 消费、再跳转模型管理归因分析验证 `factor_research` 来源上下文，普通用户提交默认模型审批请求、管理员通过待审审批请求、非管理员审批人通过 `factor.approve` 权限审核待审请求，以及审批策略关闭直接审批后操作路径切换。
- Playwright live browser E2E 已覆盖真实运行中 API：浏览器进入 `/factor-research`，注册临时用户，提交候选表达式，调用真实 evaluator，并验证候选队列回显；该用例默认跳过，通过 `LIVE_FACTOR_RESEARCH_E2E=1` 显式开启。
- Live API smoke 可通过 `--include-approval-flow` 额外验证真实数据库上的默认模型审批流：种最小 completed factor training、ready user model 与审批用户，覆盖审批策略读写、普通用户提交审批请求、重复提交幂等、管理员审核通过、拒绝请求不触发默认模型/审计、默认模型设置、审批审计落库和审批通知落库；默认清理本次种子数据，只有显式 `--keep-approval-flow-data` 才保留排障数据。
- Live API smoke 可通过 `--include-shadow-simulation-flow` 额外验证真实 DB/Redis/service 层的 Shadow Signal 模拟盘门禁：临时种策略、`qm_model_inference_runs`、`engine_signal_scores` 与 Redis 模拟账户快照，验证未授权 `factor_shadow` 返回 409，显式授权后创建 `SIMULATION` hosted task 并保留 `signal_source=factor_shadow` 审计上下文，最后清理所有种子数据。
- 外部提交门禁已有单元测试覆盖：WQ 凭证存在仍默认关闭、显式 QuantMind allow flag 后才允许、QuantGPT 研究评估端点默认可用、`/api/v1/wq-brain/submit` 在 adapter 层默认阻断。

需要补齐：

- 更完整的 run 日志流和多 worker 执行日志查看；基础 campaign item 排障字段、worker event 查询 API 和运行健康面板最近事件已在工作台展示。
- 更复杂的多级审批策略和自动执行策略；基础组织级审批策略、审批队列表、`factor.approve` 细粒度 RBAC、审批通知、审核 API、独立审计表与查询 API 已落地。
- 指标详情：IC、IR、turnover、anti-overfit、rolling validation。
- factor values 已有基础覆盖率 summary、分页抽样、空值数、异常股票代码样本、source 分布和近期日期分布；待补行业/市值/分组分位等研究维度分布统计。
- promotion gate 详情。
- 完整 campaign 页面：多 worker 进度和更细粒度策略参数。异步启动、跨 campaign generation 历史和基础策略选择已在工作台展示，可从 Campaign 历史选择具体 campaign 并查看 generation summary 与候选明细。
- “晋升为训练特征”审批按钮。
- 真实后端训练容器参与的浏览器端到端测试：当前 live browser E2E 已覆盖候选创建和真实 evaluator，尚未覆盖训练容器实际完成 promoted vs baseline 训练。
- 后台 shadow runner / 模拟盘实际执行订单、持仓重算与结果回流 E2E 已接入 `--include-shadow-simulation-flow`：执行授权 hosted task 后断言 `trade_manual_execution_tasks.status=completed`、`simulation_orders > 0`、`simulation_fills > 0`、`simulation_position_lots > 0`、`simulation_cash_ledger > 0`。

前端原则：

- 不直接调用 QuantGPT sidecar。
- 只调用 QuantMind `/api/v1/research/factors/*`。
- 所有危险动作默认 disabled，需要后端返回 capability 才能启用。

## 测试方案

### 单元测试

已存在：

- `backend/services/tests/test_quantgpt_client.py`
- `backend/services/tests/test_quantgpt_factor_mapping.py`
- `backend/services/tests/test_quantgpt_signal_adapter.py`
- `backend/services/tests/test_research_factor_service.py`

需要新增：

- `test_factor_candidate_service.py`
- `test_factor_value_store.py`
- `test_factor_campaign_service.py`：当 campaign service 从 API service 下沉到 engine service 后拆分。
- `test_factor_feature_promotion.py`
- `test_research_factor_api.py`

覆盖：

- payload contract mismatch。
- symbol normalization。
- promotion gate。
- duplicate expression hash。
- invalid factor values。
- long-only / long-short signal event。

### Fresh DB 测试

必须新增，因为本次注册和策略表问题说明现有测试没有覆盖空库启动。

建议命令：

```bash
docker compose down -v
docker compose up -d db redis quantmind
curl http://127.0.0.1:8000/health
```

验收：

- 用户注册成功。
- `/api/v1/strategies` 返回 200。
- `/api/v1/ai-ide/files/list` 返回 200。
- research factor API 启动时所需表全部存在。

### 真实数据 Smoke

已存在：

- `backend/services/engine/scripts/quantgpt_real_data_smoke.py`
- `--repeat` 会重复读取同一批真实 K 线，并比较标准化 OHLCV 指纹，验证 repeated-run 可复现性。
- `backend/services/engine/scripts/factor_research_live_api_smoke.py`
- `factor_research_live_api_smoke.py` 会调用运行中的 QuantMind API，覆盖健康检查、注册或 token 登录、策略列表、AI-IDE 文件列表、候选创建、真实 evaluator、run 回读、列表回显、feature promotion、可选 materialize、DB-only shadow signal。
- 当本地 `stock_daily_latest` 缺失时，可显式加 `--bootstrap-from-westock`，脚本会从公开 K 线补充项目本地 PostgreSQL 的最小 OHLCV 样本；默认不访问外部写库、不发布 Redis stream、不触发真实交易。

后续需要扩展为：

- 使用 QuantMind 本地 `stock_daily_latest` adapter contract。
- 固定表达式：
  - `rank(close / ts_mean(close, 20))`
  - `rank(ts_delta(close, 5) / ts_shift(close, 5))`
  - `rank(ts_corr(rank(close), rank(volume), 10))`
- 固定窗口：
  - 最近 180 个自然日。
  - 最近 2 个完整年度。
- 固定股票池：
  - hs300。
  - csi500。
  - 全 A 180 天压力测试。

通过标准：

- repeated run 指标可复现。
- symbol 100% 前缀格式。
- factor value 非空覆盖率 >= 90%。
- 不访问外部写库。
- 不发布真实交易信号。

当前运行中服务验证命令：

```bash
DATABASE_URL= DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=quantmind DB_USER=quantmind DB_PASSWORD=quantmind2026 \
python backend/services/engine/scripts/factor_research_live_api_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --bootstrap-from-westock \
  --lookback-days 60 \
  --min-symbols-per-day 5 \
  --bootstrap-limit 90 \
  --include-materialize \
  --timeout-seconds 120
```

当前服务器最近一次结果：`status=passed`，`inserted_values=2125`，`coverage_days=84`，`materialization_status=materialized`，`signal_count=5`，`stream_published_count=0`。

不带 bootstrap 的运行中服务复跑结果：`status=passed`，`strategy_total=10`，`ai_ide_file_count=10`，`inserted_values=1375`，`signal_count=5`，`stream_published_count=0`。

### E2E 测试

需要 Playwright 覆盖：

- 登录后从底部导航进入 `因子研究`。
- 创建候选因子。
- 看到 pending/running/completed 状态。
- 评估完成后看到指标。
- 未达标因子 promotion disabled。
- 达标因子可进入 promotion review。

已落地的前端 E2E：

- `electron/tests/e2e/factor-research-flow.spec.ts` 使用 mock API 验证 `/factor-research` 独立入口、候选创建、evaluation run 创建，以及 `running` 到 `completed` 的自动轮询。
- `electron/tests/e2e/factor-research-flow.spec.ts` 覆盖 completed evaluation run 读取 `/api/v1/research/factors/runs/{run_id}/values`，并在工作台回显 factor values 总量、覆盖统计、质量摘要和样本值。
- `electron/tests/e2e/factor-research-flow.spec.ts` 覆盖运行健康面板读取 `/api/v1/research/factors/health`，展示失败 run、待物化、活跃 campaign 和告警摘要；同文件覆盖默认挖掘模式下启动 bounded campaign、策略切换预览与 payload、校验 `max_generations`/metadata payload、latest campaign detail 读取、generation summary/候选历史展示、Campaign 历史切换、run/candidate id、RankIC/ICIR/Turnover、淘汰原因、进化算子/parents/evolution reason 和当前选中 campaign best candidate 晋升 payload。
- `electron/tests/e2e/factor-research-flow.spec.ts` 覆盖已物化 promotion 发起 Shadow 训练、自动 baseline payload、训练门禁通过后的默认模型审批，并在同一浏览器路径继续验证模型训练页消费 `factor_research` 特征目录、模型管理页展示因子研究来源上下文。
- `electron/tests/e2e/factor-research-flow.spec.ts` 覆盖审批策略读取/保存，并验证关闭直接审批后直审按钮禁用、审批请求入口可用。
- `electron/tests/e2e/factor-research-live.spec.ts` 默认跳过；设置 `LIVE_FACTOR_RESEARCH_E2E=1` 后连接真实 QuantMind API，验证浏览器页面提交候选、真实 evaluator 完成 run、候选队列回显。
- `electron/tests/e2e/factor-research-live.spec.ts` 设置 `LIVE_FACTOR_RESEARCH_FULL_E2E=1` 后增加扩展浏览器验收：真实点击提交评估、登记 Shadow 特征、按 promote 返回状态选择跳过或执行物化、确认进入可训练状态，并发布 Shadow Signal；该测试覆盖前端按钮到真实 promotion/materialization/signal API 的协同链路，默认不发起 Shadow 训练以避免常规 E2E 创建重训练任务。
- `electron/tests/e2e/model-training-factor-catalog.spec.ts` 覆盖模型训练页读取 active feature catalog 后展示 `factor_research` 分类和晋升因子，验证因子研究物化产物能在模型训练第一步被消费。
- `electron/tests/e2e/model-registry-factor-context.spec.ts` 覆盖模型管理归因分析页展示因子研究来源上下文。
- `backend/services/engine/scripts/factor_research_live_api_smoke.py --include-campaign-flow` 覆盖运行中 API 的 bounded 多代 campaign：创建 `max_generations=2` 的本地 mutation/crossover campaign，验证 create/detail 的 `generationStats` 和第二代 item；同一 smoke 还会创建 `run_async=true` campaign，轮询 detail 直到 completed 并断言返回 items。
- `backend/services/engine/scripts/factor_research_live_api_smoke.py --include-approval-flow` 覆盖真实 PostgreSQL/service 层审批链路：approval policy、approval request、idempotent replay、admin approve/reject review、default model、audit、notifications 和默认测试数据清理。
- `backend/services/engine/scripts/factor_research_live_api_smoke.py --include-shadow-simulation-flow` 覆盖真实 PostgreSQL/Redis/service 层 Shadow Signal 模拟盘门禁与执行回流：未授权拒绝、显式授权创建并执行 `SIMULATION` hosted task、保留 `factor_shadow` 信号来源和触发上下文，并断言 `simulation_orders/simulation_fills/simulation_position_lots/simulation_cash_ledger` 均有落库。
- 容器内完整 live smoke profile：
  `docker exec quantmind sh -lc 'DEBUG=false python backend/services/engine/scripts/factor_research_live_api_smoke.py --base-url http://127.0.0.1:8000 --full-profile --timeout-seconds 120'`
  `--full-profile` 等价于同时启用 materialize、bounded campaign、approval flow 和 shadow simulation gate；最近一次实测 `status=passed`，覆盖 candidate/evaluation/factor values/promotion/materialize/campaign/shadow signal/approval service/shadow simulation hosted flow；关键断言包括 `materialization_status=materialized`、`campaign_flow_completed_generations=2`、`approval_flow_review_status=approved`、`approval_flow_reject_status=rejected`、`shadow_simulation_unauthorized_status=409`、`shadow_simulation_authorized_trading_mode=SIMULATION`、`shadow_simulation_executed_task_status=completed`、`shadow_simulation_execution_order_count=1`、`shadow_simulation_execution_fill_count=1`、`shadow_simulation_position_lot_count=1`、`shadow_simulation_cash_ledger_count=3`、`stream_published_count=0`。
- Campaign live smoke 最近一次实测 `status=passed`，`campaign_flow_completed_generations=2`，`campaign_flow_total_candidates=4`，`campaign_flow_item_count=4`。
- `electron/playwright.config.ts` 默认以 3100 端口启动纯 Vite Web 服务，避免复用人工预览的 3000 端口或误拉起 Electron；后端开发 CORS 默认白名单包含 `127.0.0.1:3100` 和 `localhost:3100`。

## 分阶段实施计划

### Phase 0：文档和开关

- 正式文档进入 `docs/`。
- `todo/` 仅保留任务清单。
- 增加 `QUANTGPT_ENABLED`、`QUANTGPT_BASE_URL`、`QUANTGPT_TIMEOUT_SECONDS`。

### Phase 1：只读候选评估闭环

- 新增候选因子表。
- 新增 evaluation run 表。
- 新增 research factor API。
- 前端可点击提交表达式并轮询状态。

### Phase 2：QuantMind 数据口径接入

- 新增 local market data adapter。
- QuantGPT 计算使用 QuantMind 数据。
- 已支持 feature snapshot Parquet 作为 evaluator 兜底输入。
- 已支持 Qlib provider 作为 evaluator 第二层兜底输入，source 标记为 `qlib_provider`。
- 已支持 Qlib provider 生成完整 QuantGPT runner `market_df` 输入，补齐 `stock_code/amount/pct_change`。
- 禁止生产路径使用 QuantGPT 外部抓数。

### Phase 3：自动挖掘 campaign

- 已支持本地 mutation/crossover campaign：窗口 mutation 与 hybrid crossover 表达式均走白名单 evaluator；`mutation_crossover` 为默认策略，`template_mutation` 保留为仅窗口突变兼容策略。
- 已支持基础异步调度：API 传 `run_async=true` 时先创建 pending campaign，后台 task/worker 入口执行并回写 completed/failed；`claim_next_pending_factor_campaign()` 通过 `FOR UPDATE SKIP LOCKED` 原子领取任务，`backend/services/engine/scripts/factor_campaign_worker.py --once` 可作为独立 worker/cron 的最小运行入口；worker 每轮先调用 `recover_stale_running_factor_campaigns()`，按 `QUANTMIND_FACTOR_CAMPAIGN_STALE_RUNNING_MINUTES` 回收超时 running 任务；前端默认使用该模式并通过轮询刷新结果。
- 已保存 campaign 和每代候选。
- 已支持 campaign 资源配额门禁：单次候选数、每用户活动 campaign 数和每日候选预算。
- 已支持 active campaign 取消控制面：后端 `POST /api/v1/research/factors/campaigns/{campaign_id}/cancel`、前端 `取消 Campaign` 操作和 Playwright 覆盖。
- 已支持跨 campaign 候选历史查看：前端读取 `GET /api/v1/research/factors/campaigns` 展示 Campaign 历史，并按需读取 `GET /api/v1/research/factors/campaigns/{campaign_id}` 展示选中 campaign 的 generation/rank、表达式、状态和分数。
- 已支持基础 campaign run 明细查看：候选历史展示 `run_id`、`candidate_id`、RankIC/ICIR/Turnover、失败/淘汰原因、进化算子、parent expressions 和 evolution reason。
- 已支持当前选中 campaign best candidate 进入 Feature 晋升：前端复用 `POST /api/v1/research/factors/candidates/{candidate_id}/promote`，传入 `bestRunId` 和 campaign 来源 metadata。
- 已支持 bounded 本地多代 generation：`max_generations` 控制代数，quota 按 `n_candidates * max_generations` 计入单次和每日预算；summary 返回 `maxGenerations`、`completedGenerations` 和 `generationStats`。
- 已接入 QuantGPT meta-evolution 与受 evaluator 白名单保护的遗传候选输出；本地安全 mutation/crossover 仍作为默认策略。
- 已增加多 worker 并发调度、worker_id 隔离 claim、heartbeat/lease/retry 和基础 worker run 日志流；更细粒度策略参数和可视化 worker timeline 可作为后续增强。

### Phase 4：feature catalog 晋升

- 生成 shadow feature set。
- 回填 factor values。
- 已支持从 materialized promotion 调用训练入口。
- 已支持因子训练关联同步现有训练任务状态、进度和结果摘要。
- 已支持 promotion 软回滚，并从 active feature catalog 移除该因子。
- 已支持显式 baseline metrics / baseline training run 的 promoted 对比摘要。
- 已支持 promoted vs baseline 训练门禁建议、显式默认模型审批、默认模型审批独立审计，并将因子研究上下文写入模型元数据和模型管理归因页；待进一步把 SHAP 贡献结果聚合成 promoted factor 级解释。
- 已推进 Workstream C：新增 engine-side `factor_value_store.py`，承载 run values 分页查询、覆盖日期/symbol 摘要、invalid symbol 样本、source 分布和最近日期分布；factor values 写侧已统一为 `upsert_factor_values()` / `upsert_factor_values_from_select()`，本地 SQL evaluator、feature snapshot/Qlib 兜底 evaluator 复用同一套 symbol 标准化、非法 symbol 过滤和 `ON CONFLICT (run_id, trade_date, symbol)` 幂等 upsert 规则；API service 只保留兼容 wrapper，API route 直接复用 engine store。

### Phase 5：shadow signal

- 已支持 factor values 转 DB-only shadow signal。
- 已支持写 `engine_signal_scores`。
- Redis stream/latest 为显式 opt-in，服务端已要求 `allow_shadow_stream=true` 二次确认。
- runner/hosted-task 消费侧已加 `allow_factor_shadow_signals` 门禁，默认跳过或拒绝 `factor_shadow`。
- 已补模拟盘风控回归：显式授权后的 factor shadow 只进入 `SIMULATION` hosted task，并保留 `signal_source=factor_shadow` 与 `simulation_hosted_scheduler` 审计上下文。
- 已补后台 hosted runner 调度桥接回归：`process_cycle` 创建 hosted task 时会透传 `SIMULATION`、`allow_factor_shadow_signals=true`，并在 `trigger_context` 标记 `source=hosted_runner`、`signal_input=engine_signal_scores`、`signal_source_policy=factor_shadow_allowed`，用于后续任务、审计和结果回流串联。
- 已补 hosted task 执行回流回归：queued hosted task 进入 `process_task` 后会派发 `SIMULATION` 订单、在订单 `remarks` 保留 `signal_source=factor_shadow`，并把 completed `result_payload` 写回任务。
- 已补运行中服务 smoke：`factor_research_live_api_smoke.py --include-shadow-simulation-flow` 会 seed 临时策略、推理 run、`engine_signal_scores` 和 Redis 模拟账户快照，验证未授权 `factor_shadow` 返回 409，显式授权后创建并执行 `SIMULATION` hosted task，断言 `simulation_orders/simulation_fills/simulation_position_lots/simulation_cash_ledger` 均有落库，并确认所有种子数据可清理。
- 已补 dispatcher 回归：`SIMULATION` 路径必须进入 `SimulationOrderSubmissionService`，资金不足等模拟执行风控返回 `simulation_rejected`，不会直接成功；成功成交路径返回 `simulation_filled`、`order_id/trade_id/fill_price/filled_quantity`，并保留 `signal_source=factor_shadow` 审计备注。
- 后台 runner 真实执行端到端已覆盖到 hosted task 执行、订单执行、持仓批次、现金流水和任务结果回流；后续仍可补 Prometheus/SLO、容量压测和异步 worker 日志流。

### Phase 6：生产门禁

- 已补默认模型审批审计基座：`qm_factor_approval_audit`、`GET /api/v1/research/factors/approvals`、前端最近审批审计展示，以及 live smoke 路由契约检查。
- 已补审批队列基座：`qm_factor_approval_requests`、普通用户提交审批请求、管理员审核通过/拒绝、前端最近审批请求展示、前端管理员通过/拒绝请求操作，以及 `--include-approval-flow` 真实 DB/service smoke。
- 已补细粒度 RBAC：`factor.approve` 可授权非管理员审批人查看 tenant 审批队列、审核请求和直接审批默认模型；API 启动时会幂等确保该权限存在并挂到 admin 角色，前端按权限展示审批控件。
- 已补审批通知：提交审批请求时通知请求人和 tenant 内 admin/`factor.approve` 审批人，审核通过/拒绝后通知请求人；通知走统一 `notifications`/Redis Stream 发布器，失败不阻断审批主链路。
- 已补组织级审批流配置：`qm_factor_approval_policies`、`GET/PUT /api/v1/research/factors/approval-policy`、前端策略配置区、Playwright 操作路径切换测试、live smoke 策略读写校验。
- 已补回滚运维工具：`factor_research_rollback_tool.py` 支持默认 dry-run、`--execute` 正式回滚、已回滚对象跳过、结构化 JSON 输出和 MockTransport 单测。
- 已补外部提交默认关闭：`external_submit_guard.py` 和 `QuantGPTClient` endpoint guard 默认阻断 WQ BRAIN / Cloud submit，除非显式设置 `QUANTMIND_FACTOR_RESEARCH_ALLOW_EXTERNAL_SUBMIT=true`。
- 已补基础运行健康摘要：`GET /api/v1/research/factors/health` 返回状态计数、关键运行指标、campaign worker event、campaign 配额策略和告警列表；`GET /api/v1/research/factors/campaign-worker-events` 返回最近 worker event 明细；前端展示健康状态、最近 worker 事件和告警摘要，live API smoke 校验健康接口契约；Prometheus `/metrics` 暴露因子研究 health status、alert count、indicator 和 quota policy gauge。
- 已补基础容量治理测试：campaign 单次/每日/active quota 边界、bounded 多代候选计数、每日预算 warning/critical health 告警；后续仍需大规模压测和风控容量演练。
- 已补 Workstream A 第一段：新增 engine-side `factor_campaign_service.py` 作为 worker 调度入口，`factor_campaign_worker.py` 不再直接导入 API router service；worker event schema 增加 `worker_id/attempt_no/duration_ms/heartbeat_at` 并支持 `worker_id` 查询；worker CLI 支持 `--worker-id`、`--max-claims`、`--concurrency`、`--heartbeat-interval` 和 `--lease-seconds`；Campaign create contract 支持 `worker_policy/retry_policy/execution_lease` 并由服务端按 env 上限裁剪后写入 metadata/params；`worker_policy.external_worker=true` 可创建只由外部 worker 领取的 pending campaign，worker claim 会按 `workerPolicy.workerId` 隔离；前端运行健康面板展示 worker、attempt、耗时和 heartbeat 时间。
- 已补真实 worker smoke：`factor_research_live_api_smoke.py --include-campaign-worker-flow` 会创建 external-worker pending campaign、运行本地 campaign worker、验证 campaign 完成并查询 worker event；最近一次容器内实测通过，`campaign_worker_flow_processed=2`、`campaign_worker_flow_event_count=6`。
- 已将 claim、recover、worker event 写入和 worker event 查询的真实 SQL 实现迁入 `backend/services/engine/research/factor_campaign_service.py`，API service 只保留兼容 wrapper，API route 直接复用 engine service 查询入口。
- 已将 claimed campaign 执行编排、payload 多代执行、失败状态回写和 campaign summary 更新迁入 engine service，API service 只保留兼容 wrapper。
- 已补 `retryPolicy` 执行语义：worker recover 阶段会按 `maxAttempts` 和 `retryFailedAfterMinutes` 将 retryable failed campaign 重新置为 pending；worker run 日志流增加 `started/stopped` 事件，记录 worker 参数、停止原因和处理数量。
- 完整监控和告警：通知策略、告警静默/升级、SLO 面板和大规模容量压测指标面板。

## 最终闭环一次性交付计划

当前候选评估、因子值入库、Feature promotion、训练快照物化、缺失 snapshot 的本地 OHLCV baseline 补齐、自动 baseline 训练对比、训练门禁建议、显式默认模型审批、DB-only shadow signal 和模拟盘授权执行已经形成基础闭环。要达到“因子研究可与模型训练、模型管理、投研、回测和模拟盘完美协同”的最终目的，剩余工作不应继续散点推进，而应按下面 5 个 workstream 连续完成。可以在同一分支上一次性推进并最终合并，但不建议压成一个不可回滚的大提交；每个 workstream 都必须有代码、前端、测试和运行中验证。

### Workstream A：Campaign 引擎下沉和多 worker 调度

目标：让自动因子挖掘从 API 内同步服务演进为 engine 可调度服务，支持多个 worker 稳定并发执行。

当前进度：

- 已新增 engine-side `factor_campaign_service.py` 作为 worker 调度入口，worker 脚本已改为依赖该模块。
- 已扩展 worker event schema 和返回 contract：`worker_id`、`attempt_no`、`duration_ms`、`heartbeat_at`。
- `factor_campaign_worker.py` 已支持 worker id、并发 claim、max claims、heartbeat interval 和 execution lease，前端运行健康面板已展示这些字段。
- Campaign create payload 已支持 `worker_policy`、`retry_policy`、`execution_lease`，服务端会按 env 上限裁剪后写入 campaign metadata/params，前端异步 Campaign 默认传保守策略。
- external-worker pending campaign 已支持按 `workerPolicy.workerId` 隔离 claim；真实 API smoke 在默认每用户 1 个 active campaign 配额下，分两轮并发启动 2 个 external worker，验证每轮只有匹配 worker 领取目标 campaign，并产生按 worker_id 分布的 worker event。
- claim、recover、worker event 写入/查询已迁入 engine service，API service 保留兼容 wrapper。
- claimed campaign 执行编排和 payload 多代执行已迁入 engine service，API service 保留兼容 wrapper。
- `retryPolicy` 已接入 failed campaign 重试入队语义，worker run 日志流已补齐 started/stopped。

必须完成：

- 新增 `backend/services/engine/research/factor_campaign_service.py`，承载 campaign claim、执行、恢复、event 写入和失败重试逻辑；API router 只负责请求校验和响应包装。
- `qm_factor_campaign_worker_events` 扩展 `worker_id / attempt_no / duration_ms / heartbeat_at`，支持区分 worker 实例、重试次数和耗时。
- `factor_campaign_worker.py` 支持 `--worker-id`、`--max-claims`、`--concurrency`、`--heartbeat-interval`、`--retry-failed-after-minutes`，并保留 `--once` 作为 smoke 入口。
- campaign metadata 增加 `workerPolicy`、`retryPolicy`、`executionLease`，可从 API payload 设置但受服务端 quota 上限约束。
- 前端 Campaign 面板展示 worker id、attempt、最近 heartbeat、执行耗时和失败重试原因。

验收：

- 已完成：单测覆盖 worker_id 隔离 claim、`FOR UPDATE SKIP LOCKED` 原子领取、worker crash 后 stale running 自动恢复和 retry attempt。
- 已完成：运行中 smoke 分两轮启动两个 external worker，创建多个 async campaign，断言每轮只有匹配 worker 领取、campaign 均完成、worker event 按 worker_id 分布。

### Workstream B：QuantGPT meta-evolution 和表达式执行器接入

目标：把当前本地安全 `mutation_crossover` 升级为真正的 QuantGPT evolution 能力，同时保持 QuantMind 数据口径和外部提交门禁。

必须完成：

- 已完成：新增 `backend/services/engine/research/quantgpt_evolution_adapter.py`，封装 QuantGPT `mutation_engine/meta_evolution/trajectory_analyzer` 的本地调用；当前以 QuantMind evaluator 可执行模板为候选输出边界。
- 所有 evolution 输入统一走 QuantMind runner input contract：`trade_date/stock_code/open/high/low/close/volume/amount/pct_change`，禁止 QuantGPT sidecar 自行抓取生产数据。
- 已完成：支持 strategy：`mutation_crossover`、`quantgpt_meta_evolution`、`quantgpt_crossover_only`、`template_mutation`；默认仍保持本地安全策略。
- 已完成：expression guard 扩展；QuantGPT 表达式进入 campaign 前先静态检查安全 token、窗口上限、函数/字段白名单和最大嵌套深度。
- 已完成：campaign item metadata 增加 parent lineage、mutation/crossover/evolution operator、QuantGPT strategy、evolution score 和 evolution reason，并返回给前端候选历史展示；live API smoke 校验 meta-evolution item metadata。
- 已完成：campaign summary 顶层聚合 `operatorStats`、`reasonStats` 和轻量 `lineageEdges`，前端 Campaign 状态卡展示进化摘要和 lineage edge 数；更复杂的可视化图谱可作为后续增强。
- 已完成：表达式执行器扩展，当前支持价格/成交量/amount/vwap 均值偏离、动量、tanh 动量、波动率、价量滚动相关、ts_rank、decay_linear、rolling zscore、cross-sectional scale/zscore、固定 where 均值突破模板和价格均值偏离 x 动量 hybrid，保证这些候选都能被当前本地 evaluator 执行。
- Post-MVP：完整 QuantGPT 任意表达式 AST 执行器；更复杂的嵌套 AST、行业/市值中性算子、group/rank 组合、signedpower、winsorize、更多 where 条件和非白名单字段仍需继续扩展。

验收：

- 已完成：单测覆盖 QuantGPT evolution adapter 只产出 evaluator 可执行候选，并覆盖非法表达式、非白名单表达式被拒绝。
- 已完成：live API smoke 增加 `--include-meta-evolution-flow`，用于真实环境小规模 evolution 验证。
- 已完成：SQL evaluator、feature snapshot/Qlib pandas evaluator、guard 和 adapter 单测覆盖 `ts_corr/rank(volume)/ts_std/tanh momentum/amount/vwap/ts_rank/decay_linear/zscore/scale/where` 白名单。
- Post-MVP：超大窗口、非白名单字段的细粒度错误码；完整 AST 执行器接入后的真实数据验收。

### Workstream C：Factor value store 下沉和异步批量回填

目标：让 factor values 不只是 evaluation run 的副产物，而成为训练、信号、投研分析和回填任务都可复用的 engine 产物。

当前进度：

- 已新增 engine-side `factor_value_store.py`，承载 run values 分页查询、覆盖日期/symbol 摘要、invalid symbol 样本、source 分布和最近日期分布。
- API service 的 `list_factor_run_values` 已变为兼容 wrapper，API route 直接复用 engine store。
- 已统一 factor values 写侧：本地 evaluator、feature snapshot/Qlib evaluator 均复用 engine store upsert contract，保证重复评估幂等、非法 symbol 不入库，并在 metrics 中记录 inserted/invalid symbol 统计。
- 已新增 `backend/services/engine/research/factor_value_backfill.py` 和 `backend/services/engine/scripts/factor_value_backfill_job.py`，支持按 run/candidate/promotion、日期区间、universe 和 holding period 规划或执行 backfill；candidate 或带 override 的 promotion 会创建独立 `factor_value_backfill` run，已有 run 会幂等重算。
- 已新增持久化 backfill job 基座：`qm_factor_value_backfill_jobs`、`POST /api/v1/research/factors/value-backfills`、`GET /api/v1/research/factors/value-backfills` 和 `POST /api/v1/research/factors/value-backfills/{job_id}/run`。当前支持 pending/running/completed/failed/cancelled 状态、target/params/result/error/worker_id 记录和 API 立即执行。
- 已新增独立 backfill worker 基座：`qm_factor_value_backfill_events`、`GET /api/v1/research/factors/value-backfill-events`、`POST /api/v1/research/factors/value-backfills/{job_id}/cancel` 和 `backend/services/engine/scripts/factor_value_backfill_worker.py`；worker 使用 `FOR UPDATE SKIP LOCKED` 领取 pending job，记录 claimed/started/completed/failed/worker heartbeat/idle/stopped 等事件。
- 前端因子研究工作台已接入 backfill job 基础控制面：加载最近 backfill job 和 event，展示状态、target、worker、最近事件和 resolved/processed 结果，并可对最新 completed run 创建 backfill job 后立即执行或取消活跃回填；live smoke 已支持 `--include-factor-value-backfill-flow`，覆盖创建 job、backfill worker claim/execute、completed job 和 completed event；后续继续补覆盖率、失败明细和可训练状态联动。

必须完成：

- 前端 Feature 晋升面板继续补齐覆盖率、失败原因细节和可训练状态联动。
- factor values summary 增加行业/市值/分位覆盖：至少包含分位覆盖、日期覆盖、symbol 覆盖、source 分布和 top missing reasons。

验收：

- 单测覆盖重复回填幂等、部分日期失败可重试、异常 symbol 不入库。
- 已完成：live smoke 增加 `--include-factor-value-backfill-flow`，创建 backfill job，worker 执行，校验 completed job/event 和 processed run 结果；`--full-profile` 会自动包含该检查。
- 前端 Playwright 覆盖回填进度和完成后可训练状态。

### Workstream D：跨模块消费和解释闭环

目标：确保因子研究产物能被模型训练、模型管理、投研平台、回测中心和模拟盘以同一身份消费，并能解释 promoted factor 的贡献。

已完成：

- 模型训练 feature catalog 对 `factor_research` 分类增加 feature provenance：promotion id、candidate id、factor run id、表达式、物化 source、最近训练表现。
- 模型管理归因页展示 factor research 来源上下文，并与 SHAP 贡献榜同屏查看 promoted factor、baseline run 和 feature set version。
- 投研平台旧 `QuantGPT` tab 已移除，因子研究作为正交入口；factor research signal score 以 shadow signal/DB-only 产物供下游只读消费。
- 模拟盘消费 factor shadow signal 时保留 `factor_shadow` 审计上下文，贯穿 hosted task、orders、fills、position lots 和 cash ledger。

验收：

- 已完成：Playwright 跨模块 E2E 覆盖因子研究 -> 物化 -> 模型训练 -> 默认模型审批 -> 模型管理归因；live smoke 覆盖 shadow simulation hosted task、订单、成交、持仓和现金流水。
- 已完成：`promotion_id/candidate_id/run_id` 在训练、模型、信号和模拟执行链路中可追溯。
- Post-MVP：回测中心更细的 feature set 选择器和 promoted factor 级 SHAP 聚合图谱。

### Workstream E：生产门禁、SLO 和容量压测

目标：让该能力具备上线运维边界，不因自动挖掘、回填或 shadow signal 放大风险。

已完成：

- Prometheus `/metrics` 暴露 factor research health status、alert count、indicator 和 quota policy gauge。
- `GET /api/v1/research/factors/health` 已增加 SLO section：最近窗口 run/campaign 成功率、P95 campaign duration、积压 pending 数、stale running 数和回填失败数。
- 健康告警覆盖 stale run、recent failed run、campaign worker failure、daily quota exhausted/near limit、pending materialization 和 shadow stream published。
- 前端运行健康面板已增加 SLO 卡片，展示 run/campaign 成功率、P95、pending/stale/backfill failed。
- full-profile smoke 覆盖 materialize、campaign worker、meta-evolution、backfill worker、approval、shadow simulation 和 SLO health。

验收：

- 已完成：`pytest` 覆盖 SLO 计算和告警阈值。
- 已完成：live full profile 通过；`--full-profile` 自动包含 materialize、campaign worker、backfill worker、approval、shadow simulation 和 SLO health 检查。
- Post-MVP：Alertmanager 规则文档、告警静默/升级策略和大规模容量压测 JSON 报告。

### 一次性交付顺序

建议按 A -> C -> B -> D -> E 推进：

1. 先做多 worker 和日志，因为后续 meta-evolution/backfill 都依赖稳定调度。
2. 再做 factor value store 下沉和回填，因为这是训练、信号和研究分析的共享基础。
3. 再接 QuantGPT meta-evolution，避免先接进化搜索后仍受限于同步 API 和单 worker。
4. 然后补跨模块解释和消费链路，把产物真正打通到训练、模型管理、回测和模拟盘。
5. 最后做 SLO、告警和容量压测，作为上线门禁。

完成标准：

- 所有未完成 TODO 清零，或只剩明确标注为 post-MVP 的增强项。
- 后端单测、route contract、fresh DB bootstrap、live API full profile 全通过。
- 前端 typecheck、mock Playwright、升级 Node 后的 live browser E2E 全通过。
- 文档中“未完成”不再包含主链路能力，只保留可选增强项。
- 默认仍不允许外部提交、不自动进入真实交易；所有生产风险路径都有显式开关、审批和审计。
