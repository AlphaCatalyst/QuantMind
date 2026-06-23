# QuantGPT 因子挖掘整合方案

## 定位

QuantMind 对外暴露的是独立的“因子研究”能力；QuantGPT 在其中定位为当前可接入的因子研究与因子进化引擎，不替代 QuantMind 的训练、模型注册、推理、回测和交易执行主链路。

目标是把 QuantGPT 的表达式解析、因子分组回测、反过拟合验证、滚动验证、因子评分和进化搜索能力，收敛到 QuantMind 的投研、训练、信号和风控体系内。

当前状态：

- 已落地：`backend/services/engine/research/` 中的 QuantGPT adapter、payload mapping、promotion gate、signal adapter。
- 已落地：底部导航 `因子研究` 入口，路由为 `/factor-research`，前端工作台为 `electron/src/features/research/components/FactorResearchWorkbench.tsx`。
- 已落地：adapter 单元测试和真实数据只读 smoke 脚本。
- 未完成：候选因子持久化、后端 research factor API、异步任务、feature catalog 晋升、真实 signal 写入、可点击闭环。

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
QuantMind Web / AI-IDE
  -> quantmind-api /api/v1/research/factors/*
  -> quantmind-engine research service
  -> QuantGPT sidecar or embedded runner
  -> QuantMind local data adapter
  -> qm_factor_candidates / qm_factor_candidate_runs / qm_factor_values
  -> feature catalog promotion OR shadow signal publication
  -> model training / model registry / inference / simulation trading
```

### 部署边界

建议第一阶段以 sidecar 方式运行 QuantGPT：

- QuantGPT 使用内部端口 `8013`，避免和 QuantMind `stream:8003` 冲突。
- 默认配置 `QUANTGPT_ENABLED=false`，显式打开后才暴露功能。
- QuantGPT 不直接访问外部生产数据库；生产数据从 QuantMind 本地库或 feature snapshot 注入。
- WQ BRAIN、Cloud submit、外部自动提交能力默认禁用。

后续如果依赖和运行时稳定，再考虑把 QuantGPT 的表达式引擎与验证模块内嵌为 engine 子模块。

## 数据口径

### 输入数据源

生产顺序：

1. QuantMind 本地 PostgreSQL：`stock_daily_latest`。
2. QuantMind feature snapshot Parquet。
3. QuantMind Qlib 数据。
4. QuantGPT 自带缓存只允许 research 对照，不作为生产验收依据。

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

## 后端设计

### 模块结构

已存在：

- `backend/services/engine/research/quantgpt_client.py`
- `backend/services/engine/research/quantgpt_mapping.py`
- `backend/services/engine/research/factor_promotion.py`
- `backend/services/engine/research/factor_signal_adapter.py`
- `backend/services/engine/research/schemas.py`

需要补齐：

- `backend/services/engine/research/factor_candidate_service.py`
- `backend/services/engine/research/factor_campaign_service.py`
- `backend/services/engine/research/factor_value_store.py`
- `backend/services/engine/routers/research_factors.py`
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
- `trade_date`
- `symbol`
- `factor_value`
- `created_at`

建议按 `trade_date` 和 `candidate_id` 建索引；全 A 长窗口场景下再考虑分区。

### API

建议由 `quantmind-api` 代理到 `quantmind-engine`，用户态统一走 `/api/v1`。

```text
POST /api/v1/research/factors/candidates
GET  /api/v1/research/factors/candidates
GET  /api/v1/research/factors/candidates/{candidate_id}
POST /api/v1/research/factors/candidates/{candidate_id}/evaluate
GET  /api/v1/research/factors/runs/{run_id}
POST /api/v1/research/factors/candidates/{candidate_id}/compute-values
POST /api/v1/research/factors/candidates/{candidate_id}/promote
POST /api/v1/research/factors/candidates/{candidate_id}/publish-shadow-signal
POST /api/v1/research/factors/campaigns
GET  /api/v1/research/factors/campaigns/{campaign_id}
```

所有写接口必须带：

- `tenant_id`
- authenticated `user_id`
- request id / trace id
- feature flag check

### 异步任务

因子评估、全量 factor values、历史回放、promotion 训练都应异步执行。

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
2. QuantGPT 执行表达式校验、分组回测、反过拟合、滚动验证。
3. QuantMind 保存候选因子和 run 指标。
4. promotion gate 检查是否达标。
5. 通过后生成 feature definition。
6. 生成 shadow feature set version。
7. 回填历史 factor values。
8. 调用现有 `/api/v1/models/run-training`。
9. 注册新模型。
10. 和 baseline 模型同窗口对比。
11. 人工或规则审批后设为默认模型或绑定策略。

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

建议阶段：

1. 手动表达式评估。
2. 批量 seed expression 评估。
3. mutation-only campaign。
4. mutation + crossover campaign。
5. 自动触发 promotion shadow training。

## 前端整合

现有入口：

- 底部导航 `因子研究`。
- 路由：`/factor-research`。
- 页面：`electron/src/pages/FactorResearchPage.tsx`。
- 工作台组件：`electron/src/features/research/components/FactorResearchWorkbench.tsx`。
- 投研平台保留为候选池、自选、研究池工作台，不承载因子挖掘任务。

需要补齐：

- 候选因子列表。
- 评估任务创建。
- run 状态轮询。
- 指标详情：IC、IR、turnover、anti-overfit、rolling validation。
- factor values 覆盖率和 symbol invalid 统计。
- promotion gate 可视化。
- campaign 页面。
- “晋升为训练特征”审批按钮。
- “发布 shadow signal”按钮。

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

需要新增：

- `test_factor_candidate_service.py`
- `test_factor_value_store.py`
- `test_factor_campaign_service.py`
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

后续需要升级为：

- 使用 QuantMind 本地 `stock_daily_latest`。
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

### E2E 测试

需要 Playwright 覆盖：

- 登录后从底部导航进入 `因子研究`。
- 创建候选因子。
- 看到 pending/running/completed 状态。
- 评估完成后看到指标。
- 未达标因子 promotion disabled。
- 达标因子可进入 promotion review。

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
- 禁止生产路径使用 QuantGPT 外部抓数。

### Phase 3：自动挖掘 campaign

- 接入 mutation/crossover/evolution。
- 保存 campaign 和每代候选。
- 增加资源配额和并发限制。

### Phase 4：feature catalog 晋升

- 生成 shadow feature set。
- 回填 factor values。
- 调用训练入口。
- 模型注册和 baseline 对比。

### Phase 5：shadow signal

- factor values 转 signal。
- 写 `engine_signal_scores`。
- 发布 Redis stream。
- 接模拟盘/shadow runner。

### Phase 6：生产门禁

- 权限、审计、审批。
- 容量、风控、回滚。
- 监控和告警。

## 当前优先级

建议下一步先做 Phase 1：

1. 建表：`qm_factor_candidates`、`qm_factor_candidate_runs`。
2. API：`POST /api/v1/research/factors/candidates`、`POST /evaluate`、`GET /runs/{run_id}`。
3. 前端：`因子研究` 工作台接真实 API。
4. 测试：fresh-db + API contract + Playwright 基础流。

完成 Phase 1 后，再做自动挖掘 campaign。否则直接做 campaign 会缺持久化、状态管理和验收口径。
