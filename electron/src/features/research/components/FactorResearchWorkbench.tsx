import React from 'react';
import { Button, DatePicker, Input, InputNumber, Select, Segmented, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import {
  Activity,
  Beaker,
  CheckCircle2,
  Database,
  FlaskConical,
  GitBranch,
  Play,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const { Paragraph, Text } = Typography;
const { RangePicker } = DatePicker;

type LabMode = 'evaluate' | 'promote' | 'signal';

interface FactorTemplate {
  key: string;
  label: string;
  expression: string;
  family: string;
}

interface GateRow {
  key: string;
  metric: string;
  threshold: string;
  current: string;
  status: 'passed' | 'pending' | 'blocked';
}

const FACTOR_TEMPLATES: FactorTemplate[] = [
  {
    key: 'price_mean_reversion',
    label: '价格均值偏离',
    expression: 'rank(close / ts_mean(close, 20))',
    family: 'momentum',
  },
  {
    key: 'short_momentum',
    label: '短周期动量',
    expression: 'rank(ts_delta(close, 5) / ts_shift(close, 5))',
    family: 'momentum',
  },
  {
    key: 'price_volume_corr',
    label: '价量相关',
    expression: 'rank(ts_corr(rank(close), rank(volume), 10))',
    family: 'volume',
  },
];

const GATE_ROWS: GateRow[] = [
  { key: 'rank_ic', metric: 'Rank IC', threshold: '|mean| >= 0.015', current: '待评估', status: 'pending' },
  { key: 'ic_ir', metric: 'IC IR', threshold: '>= 0.15', current: '待评估', status: 'pending' },
  { key: 'turnover', metric: 'Turnover', threshold: '<= 0.35', current: '待评估', status: 'pending' },
  { key: 'monotonicity', metric: 'Monotonicity', threshold: '>= 0.60', current: '待评估', status: 'pending' },
  { key: 'anti_overfit', metric: 'Anti-overfit', threshold: '>= 60', current: '待评估', status: 'pending' },
  { key: 'coverage', metric: 'Coverage days', threshold: '>= 120', current: '待评估', status: 'pending' },
];

const statusTag = (status: GateRow['status']) => {
  if (status === 'passed') return <Tag color="success" className="m-0 rounded-full font-bold">通过</Tag>;
  if (status === 'blocked') return <Tag color="error" className="m-0 rounded-full font-bold">阻断</Tag>;
  return <Tag color="processing" className="m-0 rounded-full font-bold">待跑数</Tag>;
};

const PIPELINE_STEPS = [
  {
    icon: Beaker,
    title: '因子构思',
    value: 'Seed',
    description: '手动表达式、模板、自动挖掘 campaign',
    output: '候选表达式',
    tone: 'blue',
  },
  {
    icon: Database,
    title: '数据准备',
    value: 'Data',
    description: '股票池、窗口、OHLCV、特征快照',
    output: '标准输入集',
    tone: 'emerald',
  },
  {
    icon: FlaskConical,
    title: '计算评估',
    value: 'Eval',
    description: '因子值、分组收益、IC、换手',
    output: '评估 run',
    tone: 'violet',
  },
  {
    icon: ShieldCheck,
    title: '研究门禁',
    value: 'Gate',
    description: '反过拟合、滚动验证、覆盖率、成本',
    output: '通过/阻断',
    tone: 'amber',
  },
  {
    icon: GitBranch,
    title: '入库版本',
    value: 'Catalog',
    description: '候选、run、factor values 可追溯',
    output: 'Factor Catalog',
    tone: 'blue',
  },
  {
    icon: Sparkles,
    title: '晋升训练',
    value: 'Train',
    description: '生成 shadow feature set，再交给模型训练',
    output: '训练特征',
    tone: 'emerald',
  },
  {
    icon: Activity,
    title: '信号灰度',
    value: 'Signal',
    description: '转为 shadow signal，供回测和模拟盘验证',
    output: '信号流',
    tone: 'violet',
  },
  {
    icon: CheckCircle2,
    title: '监控回滚',
    value: 'Ops',
    description: '表现监控、版本回退、审计记录',
    output: '生产门禁',
    tone: 'amber',
  },
];

export const FactorResearchWorkbench: React.FC = () => {
  const [mode, setMode] = React.useState<LabMode>('evaluate');
  const [expression, setExpression] = React.useState(FACTOR_TEMPLATES[0].expression);
  const [universe, setUniverse] = React.useState('hs300');
  const [dateRange, setDateRange] = React.useState<[Dayjs, Dayjs]>([
    dayjs().subtract(180, 'day'),
    dayjs(),
  ]);
  const [groups, setGroups] = React.useState(5);
  const [holdingPeriod, setHoldingPeriod] = React.useState(5);

  const selectedTemplate = React.useMemo(
    () => FACTOR_TEMPLATES.find((item) => item.expression === expression),
    [expression],
  );

  const requestPreview = React.useMemo(() => ({
    expression,
    universe,
    start_date: dateRange[0]?.format('YYYY-MM-DD'),
    end_date: dateRange[1]?.format('YYYY-MM-DD'),
    n_groups: groups,
    holding_period: holdingPeriod,
    neutralize_industry: true,
    neutralize_cap: true,
  }), [dateRange, expression, groups, holdingPeriod, universe]);

  const gateColumns = React.useMemo<ColumnsType<GateRow>>(() => [
    {
      title: '门禁',
      dataIndex: 'metric',
      render: (value: string) => <span className="font-black text-slate-800">{value}</span>,
    },
    {
      title: '阈值',
      dataIndex: 'threshold',
      render: (value: string) => <span className="font-mono text-[11px] text-slate-500">{value}</span>,
    },
    {
      title: '当前值',
      dataIndex: 'current',
      render: (value: string) => <span className="text-slate-500">{value}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      align: 'center',
      width: 92,
      render: (status: GateRow['status']) => statusTag(status),
    },
  ], []);

  return (
    <div className="space-y-5 pb-2">
      <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-1 text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">Pre-training Pipeline</div>
            <h2 className="m-0 text-lg font-black text-slate-900">因子研究是模型训练的前置流水线</h2>
            <p className="m-0 mt-1 text-xs font-medium leading-6 text-slate-500">
              只有通过研究门禁并晋升为 shadow feature set 的因子，才进入模型训练的特征选择；未通过的表达式保留为候选或归档。
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs font-black text-slate-600">
            <Beaker className="h-4 w-4 text-emerald-500" />
            因子研究
            <span className="text-slate-300">/</span>
            <span className="text-blue-600">模型训练</span>
            <span className="text-slate-300">/</span>
            模型管理
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {PIPELINE_STEPS.map((step, index) => {
            const Icon = step.icon;
            const toneClass = step.tone === 'emerald'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
              : step.tone === 'violet'
                ? 'bg-violet-50 text-violet-700 border-violet-100'
                : step.tone === 'amber'
                  ? 'bg-amber-50 text-amber-700 border-amber-100'
                  : 'bg-blue-50 text-blue-700 border-blue-100';
            return (
              <div key={step.title} className="rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className={`flex h-9 w-9 items-center justify-center rounded-xl border ${toneClass}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-slate-500">
                    {String(index + 1).padStart(2, '0')} · {step.value}
                  </span>
                </div>
                <div className="text-sm font-black text-slate-900">{step.title}</div>
                <div className="mt-1 min-h-[36px] text-xs font-medium leading-5 text-slate-500">{step.description}</div>
                <div className="mt-3 rounded-xl bg-white px-3 py-2 text-[11px] font-black text-slate-600">
                  产物：{step.output}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-300/50">
                <FlaskConical className="h-5 w-5" />
              </div>
              <div>
                <h2 className="m-0 text-base font-black text-slate-900">因子研究工作台</h2>
                <p className="m-0 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Cross-module Factor Pipeline</p>
              </div>
            </div>
            <Segmented
              value={mode}
              onChange={(value) => setMode(value as LabMode)}
              options={[
                { label: '评估', value: 'evaluate' },
                { label: '晋升', value: 'promote' },
                { label: '信号', value: 'signal' },
              ]}
              className="research-next-segmented p-1"
            />
          </div>

          <div className="mb-4 grid gap-3 lg:grid-cols-3">
            {FACTOR_TEMPLATES.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setExpression(item.expression)}
                className={`rounded-2xl border p-4 text-left transition-all ${expression === item.expression
                  ? 'border-blue-200 bg-blue-50 shadow-md shadow-blue-100/70'
                  : 'border-slate-100 bg-slate-50/60 hover:border-slate-200 hover:bg-white'
                  }`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-black text-slate-800">{item.label}</span>
                  <Tag className="m-0 rounded-full border-none bg-white text-[10px] font-bold text-slate-500">{item.family}</Tag>
                </div>
                <div className="font-mono text-[11px] leading-5 text-slate-500">{item.expression}</div>
              </button>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
            <div className="space-y-3">
              <Input.TextArea
                value={expression}
                onChange={(event) => setExpression(event.target.value)}
                autoSize={{ minRows: 4, maxRows: 6 }}
                className="rounded-2xl border-slate-200 font-mono text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Select
                  value={universe}
                  onChange={setUniverse}
                  options={[
                    { value: 'hs300', label: '沪深 300' },
                    { value: 'csi500', label: '中证 500' },
                    { value: 'small_scale', label: '小样本' },
                  ]}
                  className="w-full"
                />
                <RangePicker
                  value={dateRange}
                  onChange={(value) => {
                    if (value?.[0] && value?.[1]) setDateRange([value[0], value[1]]);
                  }}
                  className="w-full rounded-xl"
                />
                <InputNumber
                  value={groups}
                  min={2}
                  max={20}
                  onChange={(value) => setGroups(value || 5)}
                  addonBefore="分组"
                  className="w-full"
                />
                <InputNumber
                  value={holdingPeriod}
                  min={1}
                  max={60}
                  onChange={(value) => setHoldingPeriod(value || 5)}
                  addonBefore="持有"
                  addonAfter="日"
                  className="w-full"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                <Activity className="h-3.5 w-3.5" />
                请求契约
              </div>
              <pre className="max-h-[178px] overflow-auto rounded-xl bg-slate-950 p-3 text-[10px] leading-5 text-slate-100">
                {JSON.stringify(requestPreview, null, 2)}
              </pre>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Tag color="success" className="m-0 rounded-full font-bold">挖掘引擎适配器已就绪</Tag>
              <Tag color="success" className="m-0 rounded-full font-bold">真实数据 Smoke 通过</Tag>
              <Tag color="processing" className="m-0 rounded-full font-bold">任务 API 待接入</Tag>
              {selectedTemplate && <Tag className="m-0 rounded-full bg-white font-bold">{selectedTemplate.label}</Tag>}
            </div>
            <Tooltip title="因子研究任务 API 固化后启用">
              <Button type="primary" icon={<Play className="h-4 w-4" />} disabled className="rounded-xl font-black">
                提交评估
              </Button>
            </Tooltip>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-500" />
              <Text className="text-sm font-black text-slate-800">能力状态</Text>
            </div>
            <div className="space-y-3">
              {[
                ['挖掘引擎适配器', '已完成'],
                ['表达式契约映射', '已完成'],
                ['信号适配器', '已完成'],
                ['真实数据 smoke', '已通过'],
                ['因子研究 API', '待挂载'],
                ['前端任务流', '待联调'],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-xs font-bold text-slate-500">{label}</span>
                  <span className={`text-xs font-black ${value === '已完成' || value === '已通过' ? 'text-emerald-600' : 'text-amber-600'}`}>{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-teal-500" />
              <Text className="text-sm font-black text-slate-800">产物去向</Text>
            </div>
            <div className="space-y-2">
              {[
                ['模型训练', '晋升为训练特征'],
                ['模型管理', '进入因子贡献与版本追踪'],
                ['智能策略', '转成可引用信号模板'],
                ['回测中心', '验证分组收益与换手成本'],
              ].map(([target, usage]) => (
                <div key={target} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="text-xs font-black text-slate-800">{target}</div>
                  <div className="mt-0.5 text-[11px] font-bold text-slate-500">{usage}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-2 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <Text className="text-sm font-black text-slate-800">真实数据 Smoke</Text>
            </div>
            <Paragraph className="mb-0 text-xs leading-6 text-slate-500">
              SH600519、SZ000001 最近 5 条日 K 已完成只读验证；10 行返回数据，symbol 规范率 100%，价格非空率 100%。
            </Paragraph>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <Text className="block text-sm font-black text-slate-900">
              {mode === 'evaluate' ? '候选因子门禁' : mode === 'promote' ? 'Feature 晋升门禁' : '灰度信号门禁'}
            </Text>
            <Text className="text-xs text-slate-400">
              {mode === 'evaluate'
                ? '与后端 factor_promotion.py 阈值保持一致'
                : mode === 'promote'
                  ? '只允许进入 shadow feature set'
                  : '只允许模拟盘或 shadow runner 消费'}
            </Text>
          </div>
          <Tag color="blue" className="m-0 rounded-full px-3 py-1 font-black">
            {mode === 'evaluate' ? 'Contract-first' : mode === 'promote' ? 'Shadow only' : 'Sim only'}
          </Tag>
        </div>
        <Table<GateRow>
          rowKey="key"
          columns={gateColumns}
          dataSource={GATE_ROWS}
          pagination={false}
          size="small"
          className="research-table"
        />
      </div>
    </div>
  );
};

export default FactorResearchWorkbench;
