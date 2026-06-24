# Research 子系统 (QuantMind Research)

本目录是 QuantMind 的**离线投研与 AI 策略进化中心**，负责模型训练、因子挖掘及前沿算法实验。

## 目录结构

### 1. [RD-Agent](./rd-agent/) (Core Engine)
集成微软开源的 RD-Agent 深度定制版，负责：
- 自动因子挖掘与优化循环。
- 基于大模型的策略生成方案。

### 2. [Data Adapter](./data_adapter/) (ETL Pipeline)
打通生产数据与投研引擎的桥梁：
- 负责从 PostgreSQL 导出行情。
- 将 CSV 转换为 Qlib 专用的高密度 `.bin` 格式。

### 3. [Factors](./factors/) (Alpha Research)
存放活跃的研究因子脚本，如基于 DeepSeek 的因子生成逻辑。

### 4. QuantGPT 因子挖掘整合
QuantGPT 将作为 QuantMind 的因子研究与因子进化引擎接入，负责候选因子表达式生成、分组回测、反过拟合验证、滚动验证、评分和自动迭代。

正式整合方案见：

- [`docs/QuantGPT因子挖掘整合方案.md`](../docs/QuantGPT因子挖掘整合方案.md)

当前已落地点：

- 后端 adapter：`backend/services/engine/research/`
- 前端入口：独立 `因子研究` 页面，路由 `/factor-research`，位于 `模型训练` 之前
- 只读真实数据 smoke：`backend/services/engine/scripts/quantgpt_real_data_smoke.py`

### 5. [Notebooks](./notebooks/) (Exploratory Analysis)
存放 Jupyter Notebooks，用于探索性数据分析 (EDA) 和模型可视化。

### 6. [Scripts](./scripts/) (Utilities)
用于模型上线推送 (`promote_model.py`) 等生产辅助脚本。

---
## 工作流建议
1. 使用 `data_adapter` 准备投研数据集。
2. 在 `rd-agent` 环境中运行自动进化实验。
3. 通过 `promote_model.py` 将最优模型同步至 `models/production/`。
