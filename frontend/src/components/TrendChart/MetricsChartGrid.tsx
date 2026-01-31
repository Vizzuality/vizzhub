import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  CartesianGrid,
} from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { SnapshotWithScores, Indicators, ScoringConfig } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

type MetricKey = keyof Indicators;
type TargetKey = keyof ScoringConfig['targets'];

interface MetricConfig {
  key: MetricKey;
  label: string;
  unit?: string;
  domain?: [number, number];
  targetKey?: TargetKey;
  lowerIsBetter?: boolean;
  isRatio?: boolean;
}

interface MetricGroup {
  title: string;
  color: string;
  metrics: MetricConfig[];
}

const METRIC_GROUPS: MetricGroup[] = [
  {
    title: 'Time',
    color: 'oklch(0.7 0.15 220)',
    metrics: [
      { key: 'spi', label: 'SPI', domain: [0, 1.5], targetKey: 'spi' },
      { key: 'on_time_milestones', label: 'On-Time Milestones', unit: '%', domain: [0, 100], targetKey: 'milestones_on_time', isRatio: true },
    ],
  },
  {
    title: 'Cost',
    color: 'oklch(0.7 0.15 140)',
    metrics: [
      { key: 'cpi', label: 'CPI', domain: [0, 1.5], targetKey: 'cpi' },
      { key: 'budget_variance', label: 'Budget Variance', unit: '%', domain: [0, 100], targetKey: 'budget_variance', isRatio: true },
    ],
  },
  {
    title: 'Quality',
    color: 'oklch(0.7 0.15 30)',
    metrics: [
      { key: 'defect_density', label: 'Defect Density', unit: '%', domain: [0, 10], targetKey: 'defect_density', lowerIsBetter: true },
      { key: 'escaped_rate', label: 'Escaped Rate', unit: '%', domain: [0, 5], targetKey: 'escaped_rate', lowerIsBetter: true },
      { key: 'mttr_hours', label: 'MTTR', unit: 'h', domain: [0, 48], targetKey: 'mttr_hours', lowerIsBetter: true },
      { key: 'governance_compliance', label: 'Governance Compliance', unit: '%', domain: [0, 100], targetKey: 'governance_compliance', isRatio: true },
    ],
  },
  {
    title: 'Value',
    color: 'oklch(0.7 0.15 270)',
    metrics: [
      { key: 'okr_impact', label: 'Strategic Impact', unit: '%', domain: [0, 100], targetKey: 'okr_impact', isRatio: true },
      { key: 'post_contract_tasks', label: 'Post-Contract Tasks', domain: [0, 10], targetKey: 'post_contract_tasks', lowerIsBetter: true },
    ],
  },
  {
    title: 'Satisfaction',
    color: 'oklch(0.7 0.15 340)',
    metrics: [
      { key: 'pm_satisfaction', label: 'PM Satisfaction', unit: '%', domain: [0, 100], targetKey: 'pm_satisfaction', isRatio: true },
      { key: 'client_satisfaction', label: 'Client Survey', unit: '%', domain: [0, 100], targetKey: 'client_satisfaction', isRatio: true },
    ],
  },
  {
    title: 'Flow',
    color: 'oklch(0.7 0.15 180)',
    metrics: [
      { key: 'lead_time_days', label: 'Lead Time', unit: 'd', domain: [0, 20], targetKey: 'lead_time_days', lowerIsBetter: true },
      { key: 'commitment_reliability', label: 'Commitment Reliability', unit: '%', domain: [0, 100], targetKey: 'commitment_reliability', isRatio: true },
      { key: 'story_review_ratio', label: 'Story Review Ratio', unit: '%', domain: [0, 100], targetKey: 'story_review_ratio', isRatio: true },
    ],
  },
  {
    title: 'Engineering',
    color: 'oklch(0.7 0.15 60)',
    metrics: [
      { key: 'pr_review_ratio', label: 'PR Review Coverage', unit: '%', domain: [0, 100], targetKey: 'pr_no_review_ratio', isRatio: true },
      { key: 'test_maturity', label: 'Test Maturity', unit: '%', domain: [0, 100], targetKey: 'test_maturity', isRatio: true },
      { key: 'arch_checklist', label: 'Architecture', unit: '%', domain: [0, 100], targetKey: 'architecture', isRatio: true },
      { key: 'pr_size_median', label: 'PR Size', unit: ' lines', domain: [0, 800], targetKey: 'pr_size_lines', lowerIsBetter: true },
      { key: 'review_turnaround_hours', label: 'Review Turnaround', unit: 'h', domain: [0, 72], targetKey: 'review_turnaround_hours', lowerIsBetter: true },
    ],
  },
  {
    title: 'DORA / Risk',
    color: 'oklch(0.7 0.15 310)',
    metrics: [
      { key: 'deployment_frequency', label: 'Deployment Frequency', unit: '/day', domain: [0, 2], targetKey: 'deployment_frequency' },
      { key: 'change_failure_rate', label: 'Change Failure Rate', unit: '%', domain: [0, 50], targetKey: 'change_failure_rate', lowerIsBetter: true },
      { key: 'high_vulns', label: 'Security Vulnerabilities', domain: [0, 10], targetKey: 'high_vuln_count', lowerIsBetter: true },
    ],
  },
];

type ChartMode = 'line' | 'bar';

interface MetricsChartGridProps {
  snapshots: SnapshotWithScores[];
  config?: ScoringConfig;
  chartMode?: ChartMode;
}

function formatPeriod(year: number, month: number): string {
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[month - 1]} ${year.toString().slice(-2)}`;
}

function formatValue(value: number | null, unit?: string): string {
  if (value === null) return '-';
  const formatted = value % 1 === 0 ? value.toString() : value.toFixed(2);
  return unit ? `${formatted}${unit}` : formatted;
}

interface TrendInfo {
  direction: 'up' | 'down' | 'flat';
  isGood: boolean;
  change: number;
}

function calculateTrend(
  data: Array<{ value: number | null }>,
  lowerIsBetter: boolean = false
): TrendInfo | null {
  const validValues = data.filter(d => d.value !== null).map(d => d.value as number);
  if (validValues.length < 2) return null;

  const current = validValues[validValues.length - 1];
  const previous = validValues[validValues.length - 2];
  const change = current - previous;
  const threshold = Math.abs(previous) * 0.01;

  let direction: 'up' | 'down' | 'flat';
  if (Math.abs(change) < threshold) {
    direction = 'flat';
  } else {
    direction = change > 0 ? 'up' : 'down';
  }

  const isGood = direction === 'flat'
    ? true
    : lowerIsBetter
      ? direction === 'down'
      : direction === 'up';

  return { direction, isGood, change };
}

interface MetricChartProps {
  data: Array<{ period: string; value: number | null }>;
  config: MetricConfig;
  color: string;
  target?: number;
  chartMode?: ChartMode;
}

function TrendIndicator({ trend }: { trend: TrendInfo | null }): JSX.Element | null {
  if (!trend) return null;

  const iconClass = "h-4 w-4";
  const colorClass = trend.isGood ? "text-green-500" : "text-red-500";

  if (trend.direction === 'flat') {
    return <Minus className={`${iconClass} text-muted-foreground`} />;
  }

  if (trend.direction === 'up') {
    return <TrendingUp className={`${iconClass} ${colorClass}`} />;
  }

  return <TrendingDown className={`${iconClass} ${colorClass}`} />;
}

function getValueColor(
  value: number | null,
  target: number | undefined,
  lowerIsBetter: boolean = false
): string {
  if (value === null || target === undefined) return 'text-foreground';
  const isGood = lowerIsBetter ? value <= target : value >= target;
  return isGood ? 'text-score-green' : 'text-score-red';
}

function MetricChart({ data, config, color, target, chartMode = 'line' }: MetricChartProps): JSX.Element {
  const hasData = data.some(d => d.value !== null);
  const latestValue = data.length > 0 ? data[data.length - 1]?.value : null;
  const trend = calculateTrend(data, config.lowerIsBetter);

  const domain = config.domain || [0, 100];
  const domainMin = domain[0];
  const domainMax = domain[1];

  const commonAxisProps = {
    tick: { fontSize: 10 },
    tickLine: { stroke: '#888' },
    axisLine: { stroke: '#888' },
  };

  const yAxisProps = {
    ...commonAxisProps,
    domain: config.domain || (['auto', 'auto'] as const),
    width: 30,
    tickFormatter: (value: number) => {
      if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
      if (value % 1 === 0) return value.toString();
      return value.toFixed(1);
    },
  };

  const tooltipContent = ({ active, payload }: { active?: boolean; payload?: Array<{ value: number; payload: { period: string } }> }) => {
    if (active && payload && payload.length) {
      const point = payload[0];
      const value = point.value as number;
      return (
        <div className="bg-popover border rounded px-3 py-2 shadow-lg">
          <div className="font-medium text-sm">{point.payload.period}</div>
          <div className="text-base font-semibold" style={{ color }}>
            {formatValue(value, config.unit)}
          </div>
          {target !== undefined && (
            <div className="text-xs text-muted-foreground mt-1">
              Target: {formatValue(target, config.unit)}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const referenceElements = target !== undefined && (
    <>
      {config.lowerIsBetter ? (
        <>
          <ReferenceArea y1={domainMin} y2={target} fill="#22c55e" fillOpacity={0.08} />
          <ReferenceArea y1={target} y2={domainMax} fill="#ef4444" fillOpacity={0.08} />
        </>
      ) : (
        <>
          <ReferenceArea y1={target} y2={domainMax} fill="#22c55e" fillOpacity={0.08} />
          <ReferenceArea y1={domainMin} y2={target} fill="#ef4444" fillOpacity={0.08} />
        </>
      )}
      <ReferenceLine y={target} stroke="#22c55e" strokeWidth={2} strokeDasharray="6 4" />
    </>
  );

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <CardTitle className="text-base font-medium">{config.label}</CardTitle>
          <div className="flex items-center gap-2">
            <TrendIndicator trend={trend} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {hasData ? (
          <ResponsiveContainer width="100%" height={160}>
            {chartMode === 'line' ? (
              <LineChart data={data} margin={{ top: 5, right: 5, bottom: 20, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#888" strokeOpacity={0.15} />
                <XAxis dataKey="period" {...commonAxisProps} />
                <YAxis {...yAxisProps} />
                {referenceElements}
                <Tooltip content={tooltipContent} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={{ r: 3, fill: color, strokeWidth: 2, stroke: '#fff' }}
                  activeDot={{ r: 5, fill: color, strokeWidth: 2, stroke: '#fff' }}
                  connectNulls
                />
              </LineChart>
            ) : (
              <BarChart data={data} margin={{ top: 5, right: 5, bottom: 20, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#888" strokeOpacity={0.15} />
                <XAxis dataKey="period" {...commonAxisProps} />
                <YAxis {...yAxisProps} />
                {referenceElements}
                <Tooltip content={tooltipContent} cursor={false} />
                <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            )}
          </ResponsiveContainer>
        ) : (
          <div className="h-[160px] flex items-center justify-center text-sm text-muted-foreground">
            No data
          </div>
        )}
        <div className="p-3 bg-muted/50 rounded-lg border space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Current</span>
            <span className={`text-2xl font-bold ${getValueColor(latestValue, target, config.lowerIsBetter)}`}>
              {formatValue(latestValue, config.unit)}
            </span>
          </div>
          {target !== undefined && (
            <div className="flex items-center justify-between pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground">KPI</span>
              <span className="text-sm text-foreground">
                {config.lowerIsBetter ? '≤' : '≥'}{formatValue(target, config.unit)}
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function MetricsChartGrid({ snapshots, config, chartMode = 'line' }: MetricsChartGridProps): JSX.Element {
  const sortedSnapshots = snapshots.slice().reverse();

  const getTarget = (metric: MetricConfig): number | undefined => {
    if (!metric.targetKey || !config) return undefined;
    const rawTarget = config.targets[metric.targetKey];
    if (rawTarget === undefined) return undefined;
    return rawTarget;
  };

  const getValue = (value: number | null, metric: MetricConfig): number | null => {
    if (value === null) return null;
    if (metric.isRatio) {
      return value * 100;
    }
    return value;
  };

  // Flatten all metrics with data into a single array
  const allMetricsWithData = METRIC_GROUPS.flatMap((group) =>
    group.metrics
      .filter(metric => sortedSnapshots.some(s => s.indicators[metric.key] !== null))
      .map(metric => ({ metric, group }))
  );

  if (allMetricsWithData.length === 0) return <></>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {allMetricsWithData.map(({ metric, group }) => {
        const chartData = sortedSnapshots.map((snapshot) => ({
          period: formatPeriod(snapshot.period_year, snapshot.period_month),
          value: getValue(snapshot.indicators[metric.key], metric),
        }));

        return (
          <MetricChart
            key={metric.key}
            data={chartData}
            config={metric}
            color={group.color}
            target={getTarget(metric)}
            chartMode={chartMode}
          />
        );
      })}
    </div>
  );
}
