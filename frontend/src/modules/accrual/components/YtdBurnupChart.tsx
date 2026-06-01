import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import { FORECAST_COLOR, RECOGNIZED_COLOR, formatAxisEur } from '@/modules/accrual/utils/chart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

interface YtdBurnupChartProps {
  readonly months: DashboardMonth[];
}

export function YtdBurnupChart({ months }: YtdBurnupChartProps): JSX.Element {
  const planTotal = months.reduce((sum, m) => sum + m.amount_eur, 0);
  let cumulative = 0;
  const data = months.map((m) => {
    if (m.status === 'recognized') cumulative += m.amount_eur;
    return {
      label: MONTHS_SHORT[m.month - 1] ?? String(m.month),
      recognized: cumulative,
      plan: planTotal,
    };
  });
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
