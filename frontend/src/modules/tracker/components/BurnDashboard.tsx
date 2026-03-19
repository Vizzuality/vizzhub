import { useMemo } from 'react';
import {
  AreaChart,
  Area,
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
import { cn } from '@/lib/utils';
import { PALETTE_HEX } from '@/shared/constants/palette';
import type { PeriodCostBreakdown } from '../types/tracker';
import { formatCurrency, shortMonth } from '../utils/constants';

interface BurnDashboardProps {
  readonly periods: PeriodCostBreakdown[];
  readonly budget: number | null;
  readonly projectEndDate: string | null;
}

interface CumulativePoint {
  date: string;
  label: string;
  cumulative: number;
  forecast: number | null;
}

interface MonthlyPoint {
  date: string;
  label: string;
  staff: number;
  nonStaff: number;
  total: number;
}

function monthsBetween(from: Date, to: Date): number {
  return (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth());
}

function formatCompact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value.toFixed(0)}`;
}

export function useChartData(
  periods: PeriodCostBreakdown[],
  projectEndDate: string | null,
): {
  cumulative: CumulativePoint[];
  monthly: MonthlyPoint[];
  totalBurn: number;
  forecastFinal: number | null;
  avgMonthlyBurn: number;
} {
  return useMemo(() => {
    const sorted = [...periods].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );

    let cum = 0;
    const cumulativeActual: CumulativePoint[] = sorted.map((p) => {
      cum += p.total;
      return {
        date: p.date,
        label: shortMonth(p.date),
        cumulative: Math.round(cum * 100) / 100,
        forecast: null,
      };
    });

    const monthly: MonthlyPoint[] = sorted.map((p) => ({
      date: p.date,
      label: shortMonth(p.date),
      staff: p.staff_cost,
      nonStaff: p.non_staff_cost,
      total: p.total,
    }));

    const totalBurn = cum;
    const monthCount = sorted.length;
    const avgMonthlyBurn = monthCount > 0 ? totalBurn / monthCount : 0;

    let forecastFinal: number | null = null;
    const cumWithForecast = [...cumulativeActual];

    if (projectEndDate && monthCount > 0) {
      const lastDate = new Date(sorted[sorted.length - 1].date + 'T00:00:00');
      const endDate = new Date(projectEndDate + 'T00:00:00');
      const remainingMonths = monthsBetween(lastDate, endDate);

      if (remainingMonths > 0) {
        forecastFinal = Math.round((totalBurn + avgMonthlyBurn * remainingMonths) * 100) / 100;

        const lastActual = cumulativeActual[cumulativeActual.length - 1];
        cumWithForecast[cumWithForecast.length - 1] = {
          ...lastActual,
          forecast: lastActual.cumulative,
        };

        let fcum = totalBurn;
        const maxForecastMonths = Math.min(remainingMonths, 24);
        for (let i = 1; i <= maxForecastMonths; i++) {
          const fDate = new Date(lastDate);
          fDate.setMonth(fDate.getMonth() + i);
          fcum += avgMonthlyBurn;
          cumWithForecast.push({
            date: fDate.toISOString().slice(0, 10),
            label: shortMonth(fDate.toISOString().slice(0, 10)),
            cumulative: 0,
            forecast: Math.round(fcum * 100) / 100,
          });
        }
      } else {
        forecastFinal = totalBurn;
      }
    }

    return {
      cumulative: cumWithForecast,
      monthly,
      totalBurn,
      forecastFinal,
      avgMonthlyBurn,
    };
  }, [periods, projectEndDate]);
}

const ACCENT_CLASSES: Record<string, string> = {
  green: 'bg-aux-neon-grass',
  red: 'bg-aux-red',
};

function KpiCard({
  label,
  value,
  sub,
  accent,
  dot = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly sub?: string;
  readonly accent?: 'green' | 'red' | 'muted';
  readonly dot?: boolean;
}): JSX.Element {
  const accentClass = accent ? ACCENT_CLASSES[accent] : undefined;

  return (
    <Card>
      <CardContent className="py-4 px-5">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">
          {label}
        </div>
        <div
          className={cn(
            'text-xl font-bold leading-tight flex items-center gap-2',
            accent === 'muted' && 'text-muted-foreground/50',
            (!accent || dot) && 'text-foreground',
            !dot && accent === 'green' && 'text-aux-neon-grass',
            !dot && accent === 'red' && 'text-aux-red',
          )}
        >
          {dot && accentClass && (
            <span
              className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', accentClass)}
            />
          )}
          {value}
        </div>
        {sub && (
          <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>
        )}
      </CardContent>
    </Card>
  );
}

interface ChartTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ dataKey?: string; value?: number; color?: string; name?: string }>;
  readonly label?: string;
}

function CumulativeTooltip({ active, payload, label }: ChartTooltipProps): JSX.Element | null {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border rounded px-3 py-2 shadow-lg text-xs space-y-1">
      <div className="font-medium">{label}</div>
      {payload.map((entry) => {
        if (entry.value == null || entry.value === 0) return null;
        const isForecast = entry.dataKey === 'forecast';
        return (
          <div key={entry.dataKey} className="flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground">
              {isForecast ? 'Forecast' : 'Actual'}:
            </span>
            <span className="font-medium">{formatCurrency(entry.value)}</span>
          </div>
        );
      })}
    </div>
  );
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

function CumulativeBurnChart({
  data,
  budget,
}: {
  readonly data: CumulativePoint[];
  readonly budget: number | null;
}): JSX.Element {
  const maxVal = Math.max(
    ...data.map((d) => Math.max(d.cumulative, d.forecast ?? 0)),
    budget ?? 0,
  );
  const yMax = Math.ceil(maxVal * 1.15);
  const hasForecast = data.some((d) => d.forecast !== null);

  return (
    <>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 10, right: 15, bottom: 5, left: 10 }}>
          <defs>
            <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE_HEX.neonGrass} stopOpacity={0.15} />
              <stop offset="95%" stopColor={PALETTE_HEX.neonGrass} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE_HEX.coolSteel} stopOpacity={0.08} />
              <stop offset="95%" stopColor={PALETTE_HEX.coolSteel} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, yMax]}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatCompact}
            width={55}
          />
          <RechartsTooltip content={<CumulativeTooltip />} />
          {budget != null && (
            <ReferenceLine
              y={budget}
              stroke={PALETTE_HEX.ashGrey}
              strokeDasharray="8 4"
              strokeWidth={1.5}
              label={{
                value: `Budget ${formatCompact(budget)}`,
                position: 'insideTopRight',
                fontSize: 11,
                fill: PALETTE_HEX.coolSteel,
                fontWeight: 500,
              }}
            />
          )}
          <Area
            type="monotone"
            dataKey="cumulative"
            stroke={PALETTE_HEX.neonGrass}
            strokeWidth={2}
            fill="url(#actualGrad)"
            dot={{ r: 2.5, fill: PALETTE_HEX.neonGrass, strokeWidth: 0 }}
            activeDot={{ r: 4, fill: PALETTE_HEX.neonGrass, strokeWidth: 2, stroke: 'white' }}
            connectNulls={false}
            name="Actual"
          />
          {hasForecast && (
            <Area
              type="monotone"
              dataKey="forecast"
              stroke={PALETTE_HEX.coolSteel}
              strokeWidth={2}
              strokeDasharray="6 3"
              fill="url(#forecastGrad)"
              dot={{ r: 2, fill: PALETTE_HEX.coolSteel, strokeWidth: 0 }}
              activeDot={{ r: 4, fill: PALETTE_HEX.coolSteel, strokeWidth: 2, stroke: 'white' }}
              connectNulls={false}
              name="Forecast"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-5 mt-2 text-[11px] text-muted-foreground justify-center">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.neonGrass }} />
          Actual
        </span>
        {hasForecast && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.coolSteel }} />
            Forecast
          </span>
        )}
        {budget != null && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.ashGrey }} />
            Budget
          </span>
        )}
      </div>
    </>
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
        <ComposedChart data={data} margin={{ top: 5, right: 15, bottom: 5, left: 10 }}>
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
          Staff
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PALETTE_HEX.ashGrey }} />
          Non-staff
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.coolSteel }} />
          Trend
        </span>
      </div>
      </CardContent>
    </Card>
  );
}

export default function BurnDashboard({
  periods,
  budget,
  projectEndDate,
}: BurnDashboardProps): JSX.Element | null {
  const { cumulative, totalBurn, forecastFinal } =
    useChartData(periods, projectEndDate);

  if (periods.length === 0) return null;

  const budgetVariance = budget != null ? budget - totalBurn : null;
  const varianceAccent = budgetVariance != null
    ? budgetVariance >= 0 ? 'green' : 'red'
    : 'muted';

  return (
    <div className="space-y-4">
      {/* KPI Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Budget"
          value={budget != null ? formatCurrency(budget) : '—'}
          accent={budget == null ? 'muted' : undefined}
        />
        <KpiCard
          label="Burn to Date"
          value={formatCurrency(totalBurn)}
          sub={budget != null ? `${((totalBurn / budget) * 100).toFixed(1)}% of budget` : undefined}
        />
        <KpiCard
          label="Forecast Final"
          value={forecastFinal != null ? formatCurrency(forecastFinal) : '—'}
          sub={forecastFinal != null && budget != null
            ? `${((forecastFinal / budget) * 100).toFixed(1)}% of budget`
            : forecastFinal == null ? 'Needs end date' : undefined}
          accent={
            forecastFinal == null ? 'muted'
              : budget != null && forecastFinal > budget ? 'red'
              : undefined
          }
          dot
        />
        <KpiCard
          label="Variance"
          value={budgetVariance != null ? formatCurrency(budgetVariance) : '—'}
          sub={budgetVariance != null
            ? budgetVariance >= 0 ? 'Under budget' : 'Over budget'
            : undefined}
          accent={varianceAccent}
          dot
        />
      </div>

      {/* Cumulative burn chart — always visible */}
      <Card>
        <CardContent className="pt-5 pb-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
            Cumulative Burn vs Budget
          </div>
          <CumulativeBurnChart data={cumulative} budget={budget} />
        </CardContent>
      </Card>
    </div>
  );
}
