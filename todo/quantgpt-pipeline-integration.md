# QuantGPT Pipeline 接入 QuantMind 方案

## 目标

将 `/data/codebase/stock/QuantGPT` 的主 pipeline 接入 QuantMind，用作因子发现、因子验证、因子迭代和候选因子晋升引擎；QuantMind 继续负责训练、模型注册、推理、信号发布、回测和交易执行闭环。

核心结论：

- QuantGPT 不应直接替换 QuantMind 的 Qlib 回测、模型训练和交易执行链路。
- QuantGPT 更适合作为 research sidecar 或内部 research module，产出候选因子表达式、因子值、评分和验证报告。
- 通过 QuantMind 的 feature catalog 和训练接口，候选因子可以晋升为正式训练特征，从而迭代模型。
- 通过 QuantMind 的 signal schema，候选因子也可以直接转成模拟盘/灰度信号，用于策略级验证。

## 当前链路判断

### QuantGPT 主要能力

- 表达式解析：`quantgpt/expression_parser.py`
- 因子分组回测：`quantgpt/backtest.py`
- 自动回测任务：`POST /api/v1/auto_backtest`
- 因子值导出：`POST /api/v1/factor_values`
- 因子评分：`quantgpt/iteration.py::compute_factor_score`
- 因子迭代：`quantgpt/iteration.py::generate_iteration_candidates`
- 因子库：`quantgpt/routes/factor_library.py`
- 批量挖掘工具：`scripts/factor_miner.py`

QuantGPT 的核心数据结构偏向：

- `trade_date`
- `stock_code`
- `factor_value`
- `daily_ret`
- 指标：Rank IC、IC IR、turnover、wq_fitness、monotonicity、anti_overfit、adversarial validation

### QuantMind 现有闭环

- 特征目录：`GET /api/v1/models/feature-catalog`
- 训练入口：`POST /api/v1/models/run-training`
- 模型注册：`backend/shared/model_registry.py`
- 推理入口：`POST /api/v1/models/inference/run`
- Pipeline 编排：`backend/services/engine/services/pipeline_service.py`
- 回测入口：`backend/services/engine/qlib_app`
- 信号入库：`engine_signal_scores`
- 信号流：`qm:signal:stream:{tenant}`
- 最新信号版本：`qm:signal:latest:{tenant}:{user}`

QuantMind 生产约束：

- 股票代码统一使用 `SH600000` 前缀格式。
- 本地数据库是训练/回测/推理的数据真源，远程行情只读。
- 新增训练特征必须进入 feature catalog 新版本，不能绕过白名单。
- 实盘/模拟盘执行侧消费的是 `symbol + score/side/quantity/price/run_id`，不消费因子表达式本身。

## 推荐架构

### 1. 旁路 Research Sidecar

先将 QuantGPT 作为独立 research sidecar 接入，不并入 QuantMind 主进程。

注意事项：

- QuantGPT 默认端口是 `8003`。
- QuantMind 的 `stream` 服务已使用 `8003`。
- 建议 QuantGPT sidecar 使用 `8013` 或内部 Docker network hostname，不暴露公网端口。

新增配置建议：

- `QUANTGPT_BASE_URL=http://quantgpt-research:8013`
- `QUANTGPT_ENABLED=false` 默认关闭
- `QUANTGPT_TIMEOUT_SECONDS=30`
- `QUANTGPT_MAX_CONCURRENT_TASKS=3`

### 2. QuantMind Adapter

在 QuantMind 中新增窄适配层，不让业务代码直接调用 QuantGPT API。

建议模块：

- `backend/services/engine/research/quantgpt_client.py`
- `backend/services/engine/research/factor_candidate_service.py`
- `backend/services/engine/research/factor_signal_adapter.py`

职责：

- 提交 QuantGPT 回测任务。
- 轮询任务结果。
- 拉取因子值。
- 将 QuantGPT 股票代码转换为 QuantMind 前缀格式。
- 将 QuantGPT 指标映射为 QuantMind 候选因子记录。
- 将通过阈值的因子值转换为 QuantMind signal 或 feature。

### 3. 数据源替换

接入初期可以允许 QuantGPT 使用自身缓存做 research smoke test，但生产链路必须逐步替换为 QuantMind 数据源。

目标数据适配：

- 输入：QuantMind `stock_daily_latest`、feature snapshot Parquet 或 Qlib 数据。
- 输出：QuantGPT 需要的 DataFrame schema：
  - `trade_date`
  - `stock_code`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
  - `amount`
  - `pct_change`

代码口径：

- QuantGPT 内部当前常用 `sh.600519`。
- QuantMind 必须落地为 `SH600519`。
- 统一使用 `backend/shared/stock_utils.py::StockCodeUtil.to_prefix()` 做入库/出信号转换。

## 两条接入路径

### 路径 A：因子晋升为训练特征

这是主路径，用于模型迭代。

流程：

1. QuantGPT 生成或接收候选因子表达式。
2. QuantGPT 对候选因子执行分组回测、IC、IR、换手、反过拟合、滚动验证。
3. QuantMind 保存候选因子与验证结果。
4. 达标候选进入人工或规则审批。
5. 审批通过后生成 feature definition。
6. 新增 feature catalog version。
7. 回填历史因子值到训练特征快照。
8. 调用 QuantMind `/api/v1/models/run-training` 重新训练。
9. 训练产物走现有模型注册。
10. 用同一区间比较旧模型、新模型、单因子信号。
11. 达标后设为默认模型或绑定到策略。

建议候选晋升阈值：

- Rank IC 均值绝对值 >= 0.015
- IC IR >= 0.15
- turnover <= 0.35
- monotonicity_score >= 0.6
- anti_overfit score >= 60
- 至少覆盖 120 个交易日
- 不与已有正式特征高度相关，相关系数阈值建议 0.85

需要新增表：

- `qm_factor_candidates`
- `qm_factor_candidate_runs`
- `qm_factor_feature_promotions`

### 路径 B：因子直接转交易/模拟信号

这是灰度验证路径，用于快速验证因子是否有执行价值，不等同于模型迭代。

流程：

1. 调用 QuantGPT `/api/v1/factor_values` 获取某日或某区间因子值。
2. 将 `factor_value` 做截面 rank/z-score。
3. 根据阈值生成 `score`。
4. Top N 生成 BUY 信号。
5. 如启用 long-short，Bottom N 生成 SELL/short 信号。
6. 写入 QuantMind `engine_signal_scores`。
7. 发布到 `qm:signal:stream:{tenant}`。
8. 更新 `qm:signal:latest:{tenant}:{user}`。
9. 交易 runner 按现有机制消费。

信号字段必须包含：

- `tenant_id`
- `user_id`
- `run_id`
- `signal_id`
- `client_order_id`
- `symbol`
- `side`
- `quantity`
- `price`
- `score`
- `signal_source`

注意：

- 这条路径只能先接模拟盘或 shadow trading。
- 实盘前必须加风控、容量、停牌过滤、涨跌停过滤、重复下单保护。

## API 设计建议

新增内部 API：

- `POST /api/v1/research/factors/evaluate`
- `GET /api/v1/research/factors/runs/{run_id}`
- `POST /api/v1/research/factors/{candidate_id}/compute-values`
- `POST /api/v1/research/factors/{candidate_id}/promote`
- `POST /api/v1/research/factors/{candidate_id}/publish-signal`

前端或 AI IDE 后续可以接入：

- 因子候选列表
- 因子回测详情
- 因子晋升审批
- 因子相关性/重复性检查
- 候选因子生成模型训练任务

## 最小实施计划

### Phase 0：准备

- 修改 QuantGPT sidecar 端口为 `8013`。
- 新增 QuantMind 配置项和 feature flag。
- 增加 QuantGPT health check。
- 明确不开启 WQ BRAIN/Cloud 上传能力。

验收：

- QuantMind 可以探测 QuantGPT health。
- 不影响现有 `api/engine/trade/stream` 服务启动。

### Phase 1：只读候选因子评估

- 实现 `QuantGPTFactorClient`。
- 实现提交、轮询、解析结果。
- 新增候选因子表和回测结果表。
- 将 QuantGPT 指标落到 QuantMind。

验收：

- 输入表达式后，QuantMind 可创建候选因子评估任务。
- 可以看到表达式、评分、Rank IC、turnover、报告 URL。
- 不写训练特征，不写交易信号。

### Phase 2：数据口径统一

- 新增 QuantMind market data adapter。
- 替换 QuantGPT baostock/akshare 抓数路径，或提供内部数据导入接口。
- 完成股票代码转换。

验收：

- 同一个表达式在固定区间内重复运行结果稳定。
- 结果中的 symbol 全部为 `SH/SZ/BJ` 前缀格式。

### Phase 3：因子晋升为 feature catalog

- 新增因子 feature definition。
- 新增 feature set version。
- 增量/全量计算因子值并生成训练快照。
- 调用现有训练入口。

验收：

- 新特征出现在 `/api/v1/models/feature-catalog`。
- 训练请求能选择新因子。
- 训练元数据记录 `feature_set_version`、`feature_columns`、`schema_checksum`。

### Phase 4：灰度信号发布

- 将因子值转换为 `engine_signal_scores`。
- 发布 Redis signal stream。
- 接入模拟盘/托管 runner 灰度消费。

验收：

- `qm:signal:latest:{tenant}:{user}` 指向新 run。
- runner 只消费最新 run。
- 模拟盘能看到由因子信号产生的调仓计划。

## 接入后测试方案

测试目标不是只证明接口能调用，而是证明三件事：

- QuantGPT 产出的因子结果在 QuantMind 数据口径下可重复。
- 候选因子能安全进入 QuantMind 的 feature/model/signal 体系。
- 灰度信号不会绕过 QuantMind 现有风控、最新版本门禁和代码格式约束。

### 0. 当前已落地的 Phase 1 测试资产

本分支已先落地只读适配层和测试骨架，范围限定在契约解析、代码格式、晋升门禁和信号事件生成，不写 feature catalog、不写
`engine_signal_scores`、不发布 Redis stream。

新增模块：

- `backend/services/engine/research/quantgpt_client.py`
  - QuantGPT sidecar 的窄 HTTP client。
  - 只暴露 health、提交评估、轮询评估、计算因子值。
- `backend/services/engine/research/quantgpt_mapping.py`
  - 解析 QuantGPT `auto_backtest` / `factor_values` payload。
  - 将 `sh.600519`、`600519.SH` 等格式统一转为 `SH600519`。
  - 非法 symbol 计入 `invalid_symbol_count`，不允许静默入库。
- `backend/services/engine/research/factor_promotion.py`
  - 实现候选因子晋升阈值判定。
- `backend/services/engine/research/factor_signal_adapter.py`
  - 将某个交易日的因子值转换为 QuantMind runner 可消费的 signal event。
  - 支持 long-only 和 long-short shadow signal。
- `backend/services/engine/scripts/quantgpt_real_data_smoke.py`
  - 使用 `westock-data` 查询真实 K 线，做只读 smoke test。
  - 不访问或修改外部数据库，不写 QuantMind DB，不发 Redis。

新增测试：

- `backend/services/tests/test_quantgpt_factor_mapping.py`
- `backend/services/tests/test_quantgpt_signal_adapter.py`
- `backend/services/tests/test_quantgpt_client.py`

已验证命令：

```bash
pytest --no-cov backend/services/tests/test_quantgpt_client.py backend/services/tests/test_quantgpt_factor_mapping.py backend/services/tests/test_quantgpt_signal_adapter.py -q
ruff check backend/services/engine/research backend/services/engine/scripts/quantgpt_real_data_smoke.py backend/services/tests/test_quantgpt_factor_mapping.py backend/services/tests/test_quantgpt_signal_adapter.py
python -m backend.services.engine.scripts.quantgpt_real_data_smoke --symbols SH600519,SZ000001 --limit 5
```

当前真实数据 smoke 结果：

```json
{
  "status": "passed",
  "source": "westock-data",
  "symbol_count": 2,
  "row_count": 10,
  "normalized_symbol_rate": 1.0,
  "non_empty_value_rate": 1.0,
  "start_date": "2026-06-16",
  "end_date": "2026-06-23",
  "errors": []
}
```

### 1. 单元测试

覆盖范围：

- QuantGPT 任务结果解析：
  - `status=completed/failed/cancelled`
  - `backtest_summary`
  - `scoring`
  - `anti_overfit`
  - `stock_factor_data`
- 股票代码转换：
  - `sh.600519 -> SH600519`
  - `sz.000001 -> SZ000001`
  - `600519.SH -> SH600519`
  - 非法代码拒绝或标记为 invalid，不允许静默入库。
- 候选因子阈值判定：
  - Rank IC
  - IC IR
  - turnover
  - monotonicity
  - anti_overfit score
  - coverage days
- 因子值转信号：
  - Top N 生成 BUY。
  - long-short 模式下 Bottom N 生成 SELL/short。
  - `score`、`side`、`quantity`、`price` 缺失时使用明确兜底或拒绝。
- feature promotion：
  - 新 feature key 命名稳定。
  - feature catalog version 增量生成。
  - 重复表达式不重复晋升。

建议测试文件：

- `backend/services/tests/test_quantgpt_client.py`
- `backend/services/tests/test_quantgpt_factor_mapping.py`
- `backend/services/tests/test_quantgpt_signal_adapter.py`
- `backend/services/tests/test_factor_feature_promotion.py`

### 2. 契约测试

QuantMind 与 QuantGPT 之间必须固定 JSON 契约，避免 QuantGPT 后续字段变化导致静默错判。

输入契约：

- evaluate request：
  - `expression`
  - `universe`
  - `start_date`
  - `end_date`
  - `n_groups`
  - `holding_period`
  - `neutralize_industry`
  - `neutralize_cap`
- factor values request：
  - `expression`
  - `universe`
  - `start_date`
  - `end_date`

输出契约：

- evaluate response 必须可映射为：
  - `candidate_id`
  - `expression`
  - `status`
  - `score`
  - `grade`
  - `rank_ic_mean`
  - `ic_ir`
  - `turnover`
  - `wq_fitness`
  - `anti_overfit`
  - `params`
- factor values response 必须可映射为：
  - `trade_date`
  - `symbol`
  - `factor_value`

契约失败处理：

- 必填字段缺失：评估 run 标记 `failed_contract_mismatch`。
- 非数值指标：保存原始 payload，派生指标置空，不允许进入晋升。
- symbol 无法转为前缀格式：该行丢弃并计入 `invalid_symbol_count`。

### 3. 真实数据 Smoke Test

可以用真实数据做，但只读开始，不要第一步就写 feature catalog 或信号流。

数据源优先级：

1. QuantMind 本地 PostgreSQL `stock_daily_latest`。
2. QuantMind feature snapshot Parquet。
3. QuantMind Qlib 数据。
4. QuantGPT 自带缓存只允许用于早期对照，不作为生产验收依据。

推荐固定测试窗口：

- 快速 smoke：最近 180 个自然日。
- 标准 smoke：最近 2 个完整年度。
- 稳定性回放：2021-01-01 到最近可用交易日。

推荐股票池：

- 第一档：`hs300` 或 QuantMind 本地沪深 300 标记。
- 第二档：`csi500`。
- 第三档：全 A 可交易股票，需先做性能评估。

第一批表达式：

- `rank(close / ts_mean(close, 20))`
- `rank(ts_delta(close, 5) / ts_shift(close, 5))`
- `rank(ts_corr(rank(close), rank(volume), 10))`

真实数据 smoke 通过标准：

- 同一表达式、同一窗口、同一数据源重复运行两次，核心指标差异为 0 或仅存在可解释浮点误差。
- 输出 symbol 100% 为 QuantMind 前缀格式。
- `factor_value` 非空覆盖率 >= 90%。
- 至少形成 2 个有效分组。
- 不访问或修改外部数据库。
- 不触发 WQ BRAIN/Cloud 上传。

### 4. 历史回放测试

用于判断候选因子是否值得晋升为训练特征。

回放切分：

- train：较早 60% 时间窗口。
- validation：中间 20% 时间窗口。
- test：最近 20% 时间窗口。

每个候选因子记录：

- 分段 Rank IC。
- 分段 IC IR。
- 分段 turnover。
- 分段 top group return。
- 样本外衰减比例。
- 与现有正式特征的相关性。

晋升前最低标准：

- test 段方向不反转，除非表达式显式标记为 reverse factor。
- test 段 Rank IC 不低于 train 段的 30%。
- 与任何已有正式特征相关性不超过 0.85。
- 缺失率、极值率、停牌股覆盖都在可接受范围内。

### 5. 训练链路集成测试

只在候选因子通过历史回放后执行。

流程：

1. 为候选因子生成临时 feature set version，例如 `qm_feature_set_quantgpt_shadow_YYYYMMDD`。
2. 生成训练快照，不覆盖当前 active feature set。
3. 调用 `/api/v1/models/run-training`。
4. 等待训练完成并注册模型。
5. 对比基线模型与新模型。

对比指标：

- validation/test Rank IC。
- TopK 命中率。
- 近 30 天方向正确率。
- 回测年化收益、最大回撤、换手。
- 推理输出覆盖率。

通过标准：

- 新模型指标不能只在 train 段改善。
- 新模型推理必须通过 `inference_contract.json` 检查。
- 训练元数据必须记录候选因子来源表达式、feature set version 和 schema checksum。

### 6. 灰度信号测试

用于路径 B，不代表模型上线。

测试步骤：

1. 使用真实数据计算某个交易日的因子值。
2. 仅写入测试 tenant/user。
3. 写入 `engine_signal_scores`。
4. 发布 `qm:signal:stream:{tenant}`。
5. 更新 `qm:signal:latest:{tenant}:{user}`。
6. 启动模拟盘或 shadow runner 消费。

通过标准：

- runner 丢弃非 latest run 的旧消息。
- 每条信号都包含 `run_id/signal_id/client_order_id/symbol/side/quantity/score`。
- 风控能正常过滤停牌、涨跌停、不可交易和重复订单。
- 不产生真实委托。

### 7. 性能与容量测试

至少覆盖三档规模：

- hs300，2 年窗口。
- csi500，2 年窗口。
- 全 A，180 天窗口。

记录：

- 数据加载耗时。
- 表达式计算耗时。
- 回测耗时。
- 内存峰值。
- factor values 输出行数。
- 单批信号发布耗时。

初始建议门槛：

- hs300 两年单表达式小于 60 秒。
- csi500 两年单表达式小于 120 秒。
- 全 A 180 天单表达式小于 180 秒。
- 任一任务失败必须可重试，不得阻塞其它服务。

### 8. 回滚测试

必须验证以下回滚动作：

- 禁用 `QUANTGPT_ENABLED` 后，不影响 QuantMind 原有训练/推理/回测。
- 删除候选因子不会删除已注册模型。
- 取消 feature promotion 后，active feature catalog 回到原版本。
- 灰度信号 run 过期后，runner 不再消费旧信号。

## 风险与限制

- 端口冲突：QuantGPT 默认 `8003`，必须改。
- 数据漂移：QuantGPT 自带缓存和外部数据源，生产必须使用 QuantMind 数据。
- 代码格式冲突：`sh.600519` 与 `SH600519` 必须统一。
- 回测指标不可直接比较：QuantGPT 是因子分组回测，QuantMind 是 Qlib 策略/模型信号回测。
- 依赖膨胀：QuantGPT 依赖 `baostock/akshare/quantstats/scipy/pyarrow` 等，需要和 QuantMind 镜像隔离或谨慎合并。
- 外部平台能力：WQ BRAIN 和 Cloud 上传默认关闭，避免引入外部提交风险。
- 生产执行风险：直接发布因子信号前必须通过模拟盘和风控门禁。

## 建议的第一批代码任务

1. 新增 `backend/services/engine/research/quantgpt_client.py`。
2. 新增 `backend/services/engine/research/schemas.py`。
3. 新增候选因子持久化表迁移。
4. 新增只读 research factor API。
5. 加单元测试覆盖：
   - QuantGPT result parsing
   - `sh.600519` -> `SH600519`
   - 指标阈值判定
   - signal event mapping
6. 用一个表达式 smoke test：
   - `rank(close / ts_mean(close, 20))`
