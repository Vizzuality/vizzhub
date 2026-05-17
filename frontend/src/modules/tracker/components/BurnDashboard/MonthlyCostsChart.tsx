import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { Card, CardContent } from '@/shared/components/ui/card';
import { PALETTE_HEX } from '@/shared/constants/palette';
import { formatCurrency } from '../../utils/constants';
import { formatCompact, type MonthlyPoint } from '../../utils/forecast';

interface ChartTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ dataKey?: string; value?: number; color?: string; name?: string }>;
  readonly label?: string;
}

function MonthlyTooltip({ active, payload, label }: ChartTooltipProps): JSX.Element | null {
  if (!active || !payload?.length) return null;
  const staff = payload.find((p) => p.dataKey === 'staff')?.value ?? 0;
  const nonStaff = payload.find((p) => p.dataKey === 'nonStaff')?.value ?? 0;
  return (
    <div className="bg-popover border rounded px-3 py-2 shadow-lg text-xs space-y-1">
      <div className="font-medium">{label}</div>
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: PALETTE_HEX.deepTeal }} />
        <span className="text-muted-foreground">Staff:</span>
        <span className="font-medium">{formatCurrency(staff)}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: PALETTE_HEX.ashGrey }} />
        <span className="text-muted-foreground">Non-staff:</span>
        <span className="font-medium">{formatCurrency(nonStaff)}</span>
      </div>
      <div className="border-t pt-1 mt-1 font-medium">
        Total: {formatCurrency(staff + nonStaff)}
      </div>
    </div>
  );
}

export function MonthlyCostsChart({
  data,
  avgMonthlyBurn,
}: {
  readonly data: MonthlyPoint[];
  readonly avgMonthlyBurn: number;
}): JSX.Element {
  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Monthly Costs Breakdown
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={data} margin={{ top: 5, right: 15, bottom: 5, left: 10 }} barCategoryGap="15%" maxBarSize={60}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatCompact}
              width={55}
            />
            <RechartsTooltip content={<MonthlyTooltip />} cursor={false} />
            {avgMonthlyBurn > 0 && (
              <ReferenceLine
                y={avgMonthlyBurn}
                stroke={PALETTE_HEX.dustGrey}
                strokeDasharray="4 3"
                strokeWidth={1}
                label={{
                  value: `Avg ${formatCompact(avgMonthlyBurn)}`,
                  position: 'insideTopRight',
                  fontSize: 10,
                  fill: PALETTE_HEX.coolSteel,
                }}
              />
            )}
            <Bar
              dataKey="staff"
              stackId="costs"
              fill={PALETTE_HEX.deepTeal}
              radius={[0, 0, 0, 0]}
              name="Staff"
            />
            <Bar
              dataKey="nonStaff"
              stackId="costs"
              fill={PALETTE_HEX.ashGrey}
              radius={[2, 2, 0, 0]}
              name="Non-staff"
            />
            <Line
              type="monotone"
              dataKey="total"
              stroke={PALETTE_HEX.coolSteel}
              strokeWidth={1.5}
              dot={false}
              name="Trend"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-5 mt-2 text-[11px] text-muted-foreground justify-center">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PALETTE_HEX.deepTeal }} />
            {'Staff'}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PALETTE_HEX.ashGrey }} />
            {'Non-staff'}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.coolSteel }} />
            {'Trend'}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
