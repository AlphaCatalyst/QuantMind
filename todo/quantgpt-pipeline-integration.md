# QuantGPT 因子挖掘整合 TODO

正式设计文档：

- [docs/QuantGPT因子挖掘整合方案.md](../docs/QuantGPT因子挖掘整合方案.md)

## 当前状态

- 已完成后端只读 adapter：
  - `backend/services/engine/research/quantgpt_client.py`
  - `backend/services/engine/research/quantgpt_mapping.py`
  - `backend/services/engine/research/factor_promotion.py`
  - `backend/services/engine/research/factor_signal_adapter.py`
- 已完成前端入口：
  - `electron/src/features/research/components/QuantGptFactorLab.tsx`
  - 投研平台 `QuantGPT` tab
- 已完成基础测试：
  - `backend/services/tests/test_quantgpt_client.py`
  - `backend/services/tests/test_quantgpt_factor_mapping.py`
  - `backend/services/tests/test_quantgpt_signal_adapter.py`
- 已完成只读真实数据 smoke：
  - `backend/services/engine/scripts/quantgpt_real_data_smoke.py`

## Phase 1：候选因子评估闭环

- [ ] 新增 `qm_factor_candidates` 表。
- [ ] 新增 `qm_factor_candidate_runs` 表。
- [ ] 新增 `backend/services/engine/research/factor_candidate_service.py`。
- [ ] 新增 `backend/services/engine/routers/research_factors.py`。
- [ ] 新增 API：
  - [ ] `POST /api/v1/research/factors/candidates`
  - [ ] `GET /api/v1/research/factors/candidates`
  - [ ] `POST /api/v1/research/factors/candidates/{candidate_id}/evaluate`
  - [ ] `GET /api/v1/research/factors/runs/{run_id}`
- [ ] 前端 QuantGPT tab 接入真实 API。
- [ ] 增加 API contract tests。
- [ ] 增加 fresh-db smoke test。

## Phase 2：QuantMind 数据口径接入

- [ ] 新增 QuantMind local market data adapter。
- [ ] 支持从 `stock_daily_latest` 导出 QuantGPT 所需 OHLCV schema。
- [ ] 支持从 feature snapshot / Qlib 数据补充计算输入。
- [ ] 禁止生产路径使用 QuantGPT 外部抓数。
- [ ] 固定 symbol 前缀格式验收。

## Phase 3：自动因子挖掘 Campaign

- [ ] 新增 `qm_factor_campaigns` 表。
- [ ] 新增 `backend/services/engine/research/factor_campaign_service.py`。
- [ ] 接入 QuantGPT mutation / crossover / evolution。
- [ ] 记录每代候选表达式、评分、淘汰原因。
- [ ] 增加 campaign 并发和资源配额。
- [ ] 前端新增 campaign 状态面板。

## Phase 4：Feature Catalog 晋升

- [ ] 新增 `qm_factor_values` 表。
- [ ] 新增 `qm_factor_feature_promotions` 表。
- [ ] 新增 factor value store。
- [ ] 生成 shadow feature set version。
- [ ] 回填历史 factor values。
- [ ] 调用 `/api/v1/models/run-training`。
- [ ] 保存 baseline vs promoted model 对比结果。
- [ ] 前端增加 promotion review。

## Phase 5：Shadow Signal 发布

- [ ] 新增 `qm_factor_signal_runs` 表。
- [ ] 将 factor values 转为 `engine_signal_scores`。
- [ ] 发布 `qm:signal:stream:{tenant}`。
- [ ] 更新 `qm:signal:latest:{tenant}:{user}`。
- [ ] 接入模拟盘 / shadow runner。
- [ ] 增加风控和 latest-run 门禁测试。

## Phase 6：生产门禁

- [ ] 增加权限、审计、审批。
- [ ] 增加 rollback 工具。
- [ ] 增加容量测试。
- [ ] 增加监控和告警。
- [ ] 默认关闭 WQ BRAIN / Cloud submit。

## 必须补的测试

- [ ] Fresh DB E2E：注册、策略列表、AI-IDE 文件列表、research factor API。
- [ ] QuantGPT contract mismatch。
- [ ] 真实数据 repeated-run 可复现性。
- [ ] Feature promotion 去重和回滚。
- [ ] Shadow signal 不绕过风控。
- [ ] Playwright：投研平台 QuantGPT tab 创建和轮询任务。
