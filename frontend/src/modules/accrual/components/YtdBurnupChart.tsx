import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import { FORECAST_COLOR, RECOGNIZED_COLOR, formatAxisEur } from '@/modules/accrual/utils/chart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

interface YtdBurnupChartProps {
  readonly months: DashboardMonth[];
}

export interface BurnupPoint {
  label: string;
  recognized: number;
  plan: number;
}

/**
 * Two running totals: `recognized` advances only on recognized months (so it plateaus
 * at today), `plan` advances every month (the planned recognition schedule, rising to
 * the year total by December). The gap ahead is the remaining recognition runway.
 */
export function buildBurnupSeries(months: DashboardMonth[]): BurnupPoint[] {
  let recognizedCumulative = 0;
  let planCumulative = 0;
  return months.map((m) => {
    planCumulative += m.amount_eur;
    if (m.status === 'recognized') recognizedCumulative += m.amount_eur;
    return {
      label: MONTHS_SHORT[m.month - 1] ?? String(m.month),
      recognized: recognizedCumulative,
      plan: planCumulative,
    };
  });
}

export function YtdBurnupChart({ months }: YtdBurnupChartProps): JSX.Element {
  const data = buildBurnupSeries(months);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
        <YAxis tickFormatter={formatAxisEur} width={56} fontSize={12} />
        <Tooltip formatter={(v: number) => formatCurrency(v)} />
        <Area
          type="monotone"
          dataKey="recognized"
          stroke={RECOGNIZED_COLOR}
          fill={RECOGNIZED_COLOR}
          fillOpacity={0.2}
        />
        <Line
          type="monotone"
          dataKey="plan"
          stroke={FORECAST_COLOR}
          strokeDasharray="4 4"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
