import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import {
  FORECAST_COLOR,
  PRIOR_YEAR_COLOR,
  RECOGNIZED_COLOR,
  formatAxisEur,
} from '@/modules/accrual/utils/chart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

interface YtdBurnupChartProps {
  readonly months: DashboardMonth[];
}

export interface BurnupPoint {
  label: string;
  recognized: number;
  plan: number;
  prevYear: number;
}

/**
 * Three running totals: `recognized` advances only on recognized months (so it plateaus
 * at today), `plan` advances every month (the planned recognition schedule, rising to
 * the year total by December), and `prevYear` is the prior year's cumulative recognition
 * over the same calendar — the YoY reference. The gap between recognized and prevYear at
 * any month says whether we are ahead of or behind last year.
 */
export function buildBurnupSeries(months: DashboardMonth[]): BurnupPoint[] {
  let recognizedCumulative = 0;
  let planCumulative = 0;
  let prevYearCumulative = 0;
  return months.map((m) => {
    planCumulative += m.amount_eur;
    prevYearCumulative += m.prev_amount_eur;
    if (m.status === 'recognized') recognizedCumulative += m.amount_eur;
    return {
      label: MONTHS_SHORT[m.month - 1] ?? String(m.month),
      recognized: recognizedCumulative,
      plan: planCumulative,
      prevYear: prevYearCumulative,
    };
  });
}

export function YtdBurnupChart({ months }: YtdBurnupChartProps): JSX.Element {
  const data = buildBurnupSeries(months);
  const hasPriorYear = months.some((m) => m.prev_amount_eur > 0);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
        <YAxis tickFormatter={formatAxisEur} width={56} fontSize={12} />
        <Tooltip formatter={(v: number) => formatCurrency(v)} />
        <Area
          type="monotone"
          dataKey="recognized"
          name="Recognized"
          stroke={RECOGNIZED_COLOR}
          fill={RECOGNIZED_COLOR}
          fillOpacity={0.2}
        />
        <Line
          type="monotone"
          dataKey="plan"
          name="Plan"
          stroke={FORECAST_COLOR}
          strokeDasharray="4 4"
          dot={false}
        />
        {hasPriorYear && (
          <Line
            type="monotone"
            dataKey="prevYear"
            name="Prior year"
            stroke={PRIOR_YEAR_COLOR}
            strokeOpacity={0.7}
            strokeDasharray="2 3"
            dot={false}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
