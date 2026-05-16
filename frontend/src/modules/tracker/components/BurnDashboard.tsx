import { useMemo } from 'react';
import { Info } from 'lucide-react';
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { cn } from '@/lib/utils';
import { PALETTE_HEX } from '@/shared/constants/palette';
import type { PeriodCostBreakdown } from '../types/tracker';
import { formatCurrency, shortMonth } from '../utils/constants';

interface BurnDashboardProps {
  readonly periods: PeriodCostBreakdown[];
  readonly budget: number | null;
  readonly projectEndDate: string | null;
  /**
   * Manual progress as a fraction in [0, 1]. When null/0/1, the EVM forecast
   * is skipped (see `useChartData` for the precise edge-case handling).
   */
  readonly percentCompleted?: number | null;
}

interface CumulativePoint {
  date: string;
  label: string;
  cumulative: number | null;
  forecast: number | null;
  eacForecast: number | null;
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

/**
 * Weighted moving average: recent months weigh more.
 * Last 3 months get weights 3, 2, 1; older months get weight 1.
 * Falls back to simple average with fewer than 2 data points.
 */
function weightedMonthlyAvg(monthlyCosts: number[]): number {
  const n = monthlyCosts.length;
  if (n === 0) return 0;
  if (n === 1) return monthlyCosts[0];

  const RECENT_WINDOW = 3;
  let weightedSum = 0;
  let totalWeight = 0;

  for (let i = 0; i < n; i++) {
    const distFromEnd = n - 1 - i;
    const weight = distFromEnd < RECENT_WINDOW ? RECENT_WINDOW - distFromEnd : 1;
    weightedSum += monthlyCosts[i] * weight;
    totalWeight += weight;
  }

  return weightedSum / totalWeight;
}

/**
 * Compute the chart's Y-axis maximum so that all rendered series participate
 * in the auto-fit, with an upper clamp on extreme overruns.
 *
 * On projects with low percent_completed, EAC_CPI = AC / percent_completed can
 * dwarf the budget and actuals (e.g. AC=€162k, pct=5% → EAC=€3.24M). Without a
 * clamp, the actual-cost area gets crushed against the X-axis; without
 * including EAC at all, the forecast line is drawn outside the visible box.
 *
 * Strategy: use the natural max of (actuals + budget + time-trend forecast +
 * EAC), then if EAC drives the max above 3 × budget, clamp at 3 × budget. The
 * end-of-line label still surfaces the real EAC value to the user.
 */
export function computeChartYMax(
  data: ReadonlyArray<{ cumulative: number | null; forecast: number | null; eacForecast: number | null }>,
  budget: number | null,
  eacCpiFinal: number | null,
): number {
  const baseMax = Math.max(
    ...data.map((d) => Math.max(d.cumulative ?? 0, d.forecast ?? 0)),
    budget ?? 0,
  );
  const naturalMax = Math.max(baseMax, eacCpiFinal ?? 0);
  if (
    budget != null &&
    budget > 0 &&
    eacCpiFinal != null &&
    eacCpiFinal > 3 * budget
  ) {
    return Math.ceil(Math.max(baseMax, 3 * budget) * 1.15);
  }
  return Math.ceil(naturalMax * 1.15);
}

function buildForecastPoints(
  lastDate: Date,
  totalBurn: number,
  weightedAvg: number,
  remainingMonths: number,
): { forecastFinal: number; points: CumulativePoint[] } {
  const forecastFinal = Math.round((totalBurn + weightedAvg * remainingMonths) * 100) / 100;
  const points: CumulativePoint[] = [];
  let fcum = totalBurn;

  for (let i = 1; i <= remainingMonths; i++) {
    const fDate = new Date(lastDate);
    fDate.setMonth(fDate.getMonth() + i);
    fcum += weightedAvg;
    points.push({
      date: fDate.toISOString().slice(0, 10),
      label: shortMonth(fDate.toISOString().slice(0, 10)),
      // null (not 0) so the Actual area stops at the last reported month —
      // Recharts breaks the line on null with connectNulls={false}.
      cumulative: null,
      forecast: Math.round(fcum * 100) / 100,
      eacForecast: null,
    });
  }

  return { forecastFinal, points };
}

/**
 * EVM-standard Estimate at Completion using the CPI method:
 *   EAC_CPI = BAC / CPI  where  CPI = EV / AC = (% complete × BAC) / AC
 *           = AC / % complete
 *
 * Returns null when any input is missing or out of range — projects
 * with no progress reported, zero spend, or no budget cannot produce
 * a meaningful EVM projection.
 */
export function computeEacCpi(
  totalBurn: number,
  budget: number | null,
  percentCompleted: number | null | undefined,
): number | null {
  if (budget == null || budget <= 0) return null;
  if (totalBurn <= 0) return null;
  if (percentCompleted == null) return null;
  if (percentCompleted <= 0 || percentCompleted > 1) return null;
  return Math.round((totalBurn / percentCompleted) * 100) / 100;
}

export function useChartData(
  periods: PeriodCostBreakdown[],
  projectEndDate: string | null,
  options?: { budget?: number | null; percentCompleted?: number | null },
): {
  cumulative: CumulativePoint[];
  monthly: MonthlyPoint[];
  totalBurn: number;
  forecastFinal: number | null;
  eacCpiFinal: number | null;
  avgMonthlyBurn: number;
} {
  const budget = options?.budget ?? null;
  const percentCompleted = options?.percentCompleted ?? null;

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
        eacForecast: null,
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

    const monthlyCosts = sorted.map((p) => p.total);
    const weightedAvg = weightedMonthlyAvg(monthlyCosts);

    let forecastFinal: number | null = null;
    const eacCpiFinal = computeEacCpi(totalBurn, budget, percentCompleted);
    const cumWithForecast = [...cumulativeActual];

    if (projectEndDate && monthCount > 0) {
      const lastDate = new Date(sorted[sorted.length - 1].date + 'T00:00:00');
      const remainingMonths = monthsBetween(
        lastDate,
        new Date(projectEndDate + 'T00:00:00'),
      );

      if (remainingMonths > 0) {
        const forecast = buildForecastPoints(lastDate, totalBurn, weightedAvg, remainingMonths);
        forecastFinal = forecast.forecastFinal;

        const lastActual = cumulativeActual[cumulativeActual.length - 1];
        cumWithForecast[cumWithForecast.length - 1] = {
          ...lastActual,
          forecast: lastActual.cumulative,
          eacForecast: eacCpiFinal != null ? lastActual.cumulative : null,
        };
        cumWithForecast.push(...forecast.points);

        if (eacCpiFinal != null) {
          // Straight line from last-actuals (totalBurn) to eacCpiFinal at the
          // last forecast point. Linearly interpolate across each forecast
          // month so the segment renders cleanly without relying on
          // connectNulls between distant points.
          const forecastCount = forecast.points.length;
          const slope = (eacCpiFinal - totalBurn) / forecastCount;
          const startIdx = cumWithForecast.length - forecastCount;
          for (let i = 0; i < forecastCount; i++) {
            const interp = totalBurn + slope * (i + 1);
            cumWithForecast[startIdx + i] = {
              ...cumWithForecast[startIdx + i],
              eacForecast: Math.round(interp * 100) / 100,
            };
          }
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
      eacCpiFinal,
      avgMonthlyBurn,
    };
  }, [periods, projectEndDate, budget, percentCompleted]);
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

const TOOLTIP_LABELS: Record<string, string> = {
  cumulative: 'Actual',
  forecast: 'Forecast (current pace)',
  eacForecast: 'Forecast (current efficiency)',
};

function CumulativeTooltip({ active, payload, label }: ChartTooltipProps): JSX.Element | null {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border rounded px-3 py-2 shadow-lg text-xs space-y-1">
      <div className="font-medium">{label}</div>
      {payload.map((entry) => {
        if (entry.value == null || entry.value === 0) return null;
        const key = entry.dataKey ?? '';
        const seriesLabel = TOOLTIP_LABELS[key] ?? 'Actual';
        return (
          <div key={key} className="flex items-center gap-2">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground">
              {seriesLabel}:
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

interface EacEndpointLabelProps {
  readonly x?: number;
  readonly y?: number;
  readonly value?: number;
  readonly chartYMax: number;
  readonly eacCpiFinal: number | null;
}

function EacEndpointLabel({
  x,
  y,
  value,
  chartYMax,
  eacCpiFinal,
}: EacEndpointLabelProps): JSX.Element | null {
  if (x == null || y == null || value == null) return null;
  // Only render on the final point of the series.
  if (eacCpiFinal == null) return null;
  if (Math.abs(value - Math.min(eacCpiFinal, chartYMax)) > 0.5) return null;
  return (
    <g transform={`translate(${x}, ${y})`}>
      <text
        x={-6}
        y={-8}
        textAnchor="end"
        fontSize={11}
        fontWeight={600}
        fill={PALETTE_HEX.amber}
      >
        {formatCompact(eacCpiFinal)}
      </text>
    </g>
  );
}

function CumulativeBurnChart({
  data,
  budget,
  eacCpiFinal,
}: {
  readonly data: CumulativePoint[];
  readonly budget: number | null;
  readonly eacCpiFinal: number | null;
}): JSX.Element {
  const yMax = computeChartYMax(data, budget, eacCpiFinal);
  const hasForecast = data.some((d) => d.forecast !== null);
  const hasEacForecast = data.some((d) => d.eacForecast !== null);
  // Clamp the rendered EAC series so the line stays inside the plot box when
  // EAC > 3 × budget. The endpoint label still shows the real value.
  const renderData = data.map((d) =>
    d.eacForecast != null && d.eacForecast > yMax
      ? { ...d, eacForecast: yMax }
      : d,
  );

  return (
    <>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={renderData} margin={{ top: 10, right: 15, bottom: 5, left: 10 }}>
          <defs>
            <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE_HEX.neonGrass} stopOpacity={0.15} />
              <stop offset="95%" stopColor={PALETTE_HEX.neonGrass} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={PALETTE_HEX.dustGrey} stopOpacity={0.06} />
              <stop offset="95%" stopColor={PALETTE_HEX.dustGrey} stopOpacity={0} />
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
              stroke={PALETTE_HEX.dustGrey}
              strokeWidth={1.5}
              strokeDasharray="4 6"
              fill="url(#forecastGrad)"
              dot={false}
              activeDot={{ r: 3, fill: PALETTE_HEX.dustGrey, strokeWidth: 0 }}
              connectNulls={false}
              name="Forecast (current pace)"
            />
          )}
          {hasEacForecast && (
            <Area
              type="linear"
              dataKey="eacForecast"
              stroke={PALETTE_HEX.amber}
              strokeWidth={2}
              strokeDasharray="2 4"
              fill="none"
              dot={false}
              activeDot={{ r: 3, fill: PALETTE_HEX.amber, strokeWidth: 0 }}
              connectNulls
              isAnimationActive={false}
              name="Forecast (current efficiency)"
              label={(props: EacEndpointLabelProps) => (
                <EacEndpointLabel
                  {...props}
                  chartYMax={yMax}
                  eacCpiFinal={eacCpiFinal}
                />
              )}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-2 text-[11px] text-muted-foreground justify-center">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.neonGrass }} />
          {'Actual'}
        </span>
        {hasForecast && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.dustGrey }} />
            {'Forecast (current pace)'}
          </span>
        )}
        {hasEacForecast && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.amber }} />
            {'Forecast (current efficiency)'}
          </span>
        )}
        {budget != null && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-0.5 rounded" style={{ backgroundColor: PALETTE_HEX.ashGrey }} />
            {'Budget'}
          </span>
        )}
      </div>
    </>
  );
}

function ForecastInfoPopover(): JSX.Element {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        aria-label="About the forecasts"
        className="inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors focus:outline-none focus:ring-1 focus:ring-ring rounded-sm"
      >
        <Info className="w-3.5 h-3.5" />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 text-xs space-y-3">
        <div>
          <div className="font-medium text-sm mb-1">About the forecasts</div>
          <p className="text-muted-foreground">
            Two ways to project the final cost. They answer different questions.
          </p>
        </div>
        <div>
          <div className="font-medium">Forecast (current pace)</div>
          <p className="text-muted-foreground">
            Projects total cost assuming spending continues at the recent
            monthly burn rate. Calendar-based. Useful when efficiency is
            roughly stable.
          </p>
        </div>
        <div>
          <div className="font-medium">Forecast (current efficiency)</div>
          <p className="text-muted-foreground">
            Projects total cost assuming each euro keeps delivering the same
            value as so far. Standard Earned Value Management formula:{' '}
            <code className="text-[10px]">EAC = BAC / CPI</code> where{' '}
            <code className="text-[10px]">CPI = (% complete × budget) / cost-to-date</code>.
            Reacts when value delivery lags spend; flags overruns earlier in
            projects with growing technical debt. Hidden when progress, budget,
            or cost are unavailable.
          </p>
        </div>
      </PopoverContent>
    </Popover>
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

type KpiAccent = 'green' | 'red' | 'muted';

function getVarianceAccent(variance: number | null): KpiAccent {
  if (variance == null) return 'muted';
  return variance >= 0 ? 'green' : 'red';
}

function getForecastSub(
  forecastFinal: number | null,
  budget: number | null,
): string | undefined {
  if (forecastFinal != null && budget != null) {
    return `${((forecastFinal / budget) * 100).toFixed(1)}% of budget`;
  }
  if (forecastFinal == null) return 'Needs end date';
  return undefined;
}

function getForecastAccent(
  forecastFinal: number | null,
  budget: number | null,
): KpiAccent | undefined {
  if (forecastFinal == null) return 'muted';
  if (budget != null && forecastFinal > budget) return 'red';
  return undefined;
}

function getVarianceSub(variance: number | null): string | undefined {
  if (variance == null) return undefined;
  return variance >= 0 ? 'Under budget' : 'Over budget';
}

export default function BurnDashboard({
  periods,
  budget,
  projectEndDate,
  percentCompleted = null,
}: BurnDashboardProps): JSX.Element | null {
  const { cumulative, totalBurn, forecastFinal, eacCpiFinal } = useChartData(
    periods,
    projectEndDate,
    { budget, percentCompleted },
  );

  if (periods.length === 0) return null;

  const budgetVariance = budget != null ? budget - totalBurn : null;

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
          sub={getForecastSub(forecastFinal, budget)}
          accent={getForecastAccent(forecastFinal, budget)}
          dot
        />
        <KpiCard
          label="Variance"
          value={budgetVariance != null ? formatCurrency(budgetVariance) : '—'}
          sub={getVarianceSub(budgetVariance)}
          accent={getVarianceAccent(budgetVariance)}
          dot
        />
      </div>

      {/* Cumulative burn chart — always visible */}
      <Card>
        <CardContent className="pt-5 pb-4">
          <div className="flex items-center gap-2 mb-4">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Cumulative Burn vs Budget
            </div>
            <ForecastInfoPopover />
          </div>
          <CumulativeBurnChart data={cumulative} budget={budget} eacCpiFinal={eacCpiFinal} />
        </CardContent>
      </Card>
    </div>
  );
}
