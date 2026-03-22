import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

const FA_COLORS: Record<string, string> = {
  FE: '#3b82f6',
  BE: '#10b981',
  Design: '#f59e0b',
  PM: '#8b5cf6',
  Sci: '#ef4444',
  Coms: '#06b6d4',
};

const FA_ORDER = ['FE', 'BE', 'Design', 'PM', 'Sci', 'Coms'];

interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}

function formatMonth(period: string): string {
  const [year, month] = period.split('-');
  const date = new Date(Number(year), Number(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

function transformData(data: PeriodInsight[]): ChartDataPoint[] {
  return data.map((period) => {
    const point: ChartDataPoint = { month: formatMonth(period.period) };
    for (const fa of period.functional_areas) {
      point[`${fa.short}_projects`] = Math.round(fa.billable_pct * 100);
      point[`${fa.short}_others`] = Math.round((1 - fa.billable_pct) * 100);
      point[`${fa.short}_users`] = fa.user_count;
    }
    return point;
  });
}

interface InsightsChartProps {
  readonly data: PeriodInsight[];
}

export function InsightsChart({ data }: InsightsChartProps): JSX.Element {
  const chartData = useMemo(() => transformData(data), [data]);

  const activeFAs = useMemo(() => {
    const found = new Set<string>();
    for (const period of data) {
      for (const fa of period.functional_areas) {
        found.add(fa.short);
      }
    }
    return FA_ORDER.filter((fa) => found.has(fa));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        No data for the selected period
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={450}>
      <BarChart data={chartData} barCategoryGap="15%" barGap={1}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(v: number) => `${v}%`}
          tick={{ fontSize: 12 }}
        />
        <RechartsTooltip
          formatter={(value: number, name: string) => {
            const [fa, type] = name.split('_');
            const label = type === 'projects' ? `${fa} Projects` : `${fa} Others`;
            return [`${value}%`, label];
          }}
          labelFormatter={(label: string) => label}
        />
        <Legend
          formatter={(value: string) => {
            const [fa, type] = value.split('_');
            return type === 'projects' ? `${fa} Projects` : `${fa} Others`;
          }}
        />
        {activeFAs.map((fa) => (
          <Bar
            key={`${fa}_projects`}
            dataKey={`${fa}_projects`}
            stackId={fa}
            fill={FA_COLORS[fa]}
            name={`${fa}_projects`}
          />
        ))}
        {activeFAs.map((fa) => (
          <Bar
            key={`${fa}_others`}
            dataKey={`${fa}_others`}
            stackId={fa}
            fill={FA_COLORS[fa]}
            fillOpacity={0.3}
            name={`${fa}_others`}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
