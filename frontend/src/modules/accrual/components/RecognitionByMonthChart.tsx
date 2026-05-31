import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import { MONTHS_SHORT } from '@/shared/constants/dates';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

interface RecognitionByMonthChartProps {
  readonly months: DashboardMonth[];
}

const RECOGNIZED_COLOR = 'var(--score-green)';
const FORECAST_COLOR = 'var(--muted-foreground)';

export function RecognitionByMonthChart({ months }: RecognitionByMonthChartProps): JSX.Element {
  const data = months.map((m) => ({
    label: MONTHS_SHORT[m.month - 1] ?? String(m.month),
    amount: m.amount_eur,
    recognized: m.status === 'closed',
  }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
        <YAxis tickFormatter={(v: number) => formatCurrency(v)} width={80} fontSize={12} />
        <Tooltip formatter={(v: number) => formatCurrency(v)} />
        <Bar dataKey="amount" radius={[3, 3, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.label} fill={d.recognized ? RECOGNIZED_COLOR : FORECAST_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
