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

const workflowSteps = [
  { icon: Beaker, title: '表达式评估', value: 'Phase 1', tone: 'blue' },
  { icon: Database, title: '真实数据 Smoke', value: 'Passed', tone: 'emerald' },
  { icon: GitBranch, title: 'Feature 晋升', value: 'Shadow', tone: 'violet' },
  { icon: ShieldCheck, title: '灰度信号', value: 'Sim only', tone: 'amber' },
];

export const QuantGptFactorLab: React.FC = () => {
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
      <div className="grid gap-3 md:grid-cols-4">
        {workflowSteps.map((step) => {
          const Icon = step.icon;
          const toneClass = step.tone === 'emerald'
            ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
            : step.tone === 'violet'
              ? 'bg-violet-50 text-violet-700 border-violet-100'
              : step.tone === 'amber'
                ? 'bg-amber-50 text-amber-700 border-amber-100'
                : 'bg-blue-50 text-blue-700 border-blue-100';
          return (
            <div key={step.title} className="rounded-2xl border border-slate-100 bg-white/80 p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <span className={`flex h-9 w-9 items-center justify-center rounded-xl border ${toneClass}`}>
                  <Icon className="h-4 w-4" />
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-slate-500">
                  {step.value}
                </span>
              </div>
              <div className="text-sm font-black text-slate-900">{step.title}</div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-300/50">
                <FlaskConical className="h-5 w-5" />
              </div>
              <div>
                <h2 className="m-0 text-base font-black text-slate-900">QuantGPT 因子实验室</h2>
                <p className="m-0 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Factor Research Sidecar</p>
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
              <Tag color="success" className="m-0 rounded-full font-bold">Adapter ready</Tag>
              <Tag color="success" className="m-0 rounded-full font-bold">Real-data smoke passed</Tag>
              <Tag color="processing" className="m-0 rounded-full font-bold">API router pending</Tag>
              {selectedTemplate && <Tag className="m-0 rounded-full bg-white font-bold">{selectedTemplate.label}</Tag>}
            </div>
            <Tooltip title="后端 research router 固化后启用">
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
              <Text className="text-sm font-black text-slate-800">接入状态</Text>
            </div>
            <div className="space-y-3">
              {[
                ['QuantGPT client', '已完成'],
                ['Payload mapping', '已完成'],
                ['Signal adapter', '已完成'],
                ['真实数据 smoke', '已通过'],
                ['Research API', '待挂载'],
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

export default QuantGptFactorLab;
