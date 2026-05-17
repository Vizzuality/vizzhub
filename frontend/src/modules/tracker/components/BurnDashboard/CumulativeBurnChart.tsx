import { Info } from 'lucide-react';
import {
  AreaChart,
  Area,
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
import { PALETTE_HEX } from '@/shared/constants/palette';
import { formatCurrency } from '../../utils/constants';
import {
  computeChartYMax,
  formatCompact,
  type CumulativePoint,
} from '../../utils/forecast';

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

interface EacAreaLabelProps {
  readonly x?: number;
  readonly y?: number;
  readonly payload?: { eacEndValue?: number };
}

function EacAreaLabel({ x, y, payload }: EacAreaLabelProps): JSX.Element | null {
  if (x == null || y == null) return null;
  const eacEndValue = payload?.eacEndValue;
  // Only the terminal forecast point carries `eacEndValue` — earlier
  // EAC-line points don't, so the label silently no-ops there.
  if (eacEndValue == null) return null;
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
        {formatCompact(eacEndValue)}
      </text>
    </g>
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

function CumulativeBurnChartInner({
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
  // EAC > 3 × budget. The terminal point retains its `eacEndValue` field so
  // the label still surfaces the real (unclamped) projection to the user.
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
              label={EacAreaLabel}
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

export function CumulativeBurnCard({
  data,
  budget,
  eacCpiFinal,
}: {
  readonly data: CumulativePoint[];
  readonly budget: number | null;
  readonly eacCpiFinal: number | null;
}): JSX.Element {
  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center gap-2 mb-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Cumulative Burn vs Budget
          </div>
          <ForecastInfoPopover />
        </div>
        <CumulativeBurnChartInner data={data} budget={budget} eacCpiFinal={eacCpiFinal} />
      </CardContent>
    </Card>
  );
}
