import { useMemo, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { cn } from '@/lib/utils';
import type { MetricsWithScores } from '../../types';

interface Period {
  year: number;
  month: number;
}

interface InteractiveTimelineChartProps {
  projectStartDate: string;
  snapshots: MetricsWithScores[] | undefined;
  selectedPeriod: Period | null;
  onPeriodChange: (period: Period | null) => void;
  isCapturing?: boolean;
}

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function formatPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

function formatShortPeriod(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} '${String(year).slice(2)}`;
}

function generateMonthRange(startDate: string): Period[] {
  const start = new Date(startDate);
  const now = new Date();
  const periods: Period[] = [];

  let year = start.getFullYear();
  let month = start.getMonth() + 1;

  while (
    year < now.getFullYear() ||
    (year === now.getFullYear() && month <= now.getMonth() + 1)
  ) {
    periods.push({ year, month });
    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return periods;
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'hsl(var(--muted-foreground))';
  if (score >= 80) return 'hsl(var(--score-green))';
  if (score >= 60) return 'hsl(var(--score-yellow))';
  return 'hsl(var(--score-red))';
}

interface ChartDataPoint {
  key: string;
  label: string;
  year: number;
  month: number;
  score: number | null;
  hasData: boolean;
}

export default function InteractiveTimelineChart({
  projectStartDate,
  snapshots,
  selectedPeriod,
  onPeriodChange,
  isCapturing = false,
}: InteractiveTimelineChartProps): JSX.Element {
  const periods = useMemo(
    () => generateMonthRange(projectStartDate),
    [projectStartDate],
  );

  const snapshotMap = useMemo(() => {
    const map = new Map<string, MetricsWithScores>();
    snapshots?.forEach((s) => {
      map.set(`${s.period_year}-${s.period_month}`, s);
    });
    return map;
  }, [snapshots]);

  const chartData = useMemo((): ChartDataPoint[] => {
    return periods.map((p) => {
      const key = `${p.year}-${p.month}`;
      const snapshot = snapshotMap.get(key);
      return {
        key,
        label: formatShortPeriod(p.year, p.month),
        year: p.year,
        month: p.month,
        score: snapshot?.scores?.score ?? null,
        hasData: !!snapshot,
      };
    });
  }, [periods, snapshotMap]);

  const latestWithData = useMemo((): Period => {
    for (let i = periods.length - 1; i >= 0; i--) {
      const p = periods[i];
      if (snapshotMap.has(`${p.year}-${p.month}`)) {
        return p;
      }
    }
    return periods[periods.length - 1];
  }, [periods, snapshotMap]);

  const effectivePeriod = selectedPeriod ?? latestWithData;

  const handleClick = useCallback(
    (data: ChartDataPoint) => {
      onPeriodChange({ year: data.year, month: data.month });
    },
    [onPeriodChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      const currentIndex = periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      );

      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex - 1]);
      } else if (e.key === 'ArrowRight' && currentIndex < periods.length - 1) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex + 1]);
      }
    },
    [periods, effectivePeriod, onPeriodChange],
  );

  const currentScore = useMemo(() => {
    const key = `${effectivePeriod.year}-${effectivePeriod.month}`;
    return snapshotMap.get(key)?.scores?.score ?? null;
  }, [effectivePeriod, snapshotMap]);

  const tickInterval = periods.length > 24 ? 5 : periods.length > 12 ? 2 : 0;

  return (
    <div
      className="w-full"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="slider"
      aria-label="Timeline period selector"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="text-sm text-muted-foreground">
          {formatPeriod(periods[0].year, periods[0].month)} — {formatPeriod(periods[periods.length - 1].year, periods[periods.length - 1].month)}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">
            {formatPeriod(effectivePeriod.year, effectivePeriod.month)}
          </span>
          {currentScore !== null && (
            <span
              className="text-lg font-bold"
              style={{ color: getScoreColor(currentScore) }}
            >
              {Math.round(currentScore)}
            </span>
          )}
          {currentScore === null && (
            <span className="text-sm text-muted-foreground">No data</span>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className={cn('h-24 w-full', isCapturing && 'opacity-50')}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            onClick={(e) => {
              if (e?.activePayload?.[0]?.payload) {
                handleClick(e.activePayload[0].payload as ChartDataPoint);
              }
            }}
          >
            <defs>
              <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              interval={tickInterval}
            />
            <YAxis
              domain={[0, 100]}
              hide
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const data = payload[0].payload as ChartDataPoint;
                return (
                  <div className="bg-popover border border-border rounded-md px-3 py-2 shadow-md">
                    <p className="text-sm font-medium">{formatPeriod(data.year, data.month)}</p>
                    {data.hasData ? (
                      <p className="text-lg font-bold" style={{ color: getScoreColor(data.score) }}>
                        Score: {Math.round(data.score!)}
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">No data available</p>
                    )}
                  </div>
                );
              }}
            />
            <ReferenceLine
              x={formatShortPeriod(effectivePeriod.year, effectivePeriod.month)}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              strokeDasharray="3 3"
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              fill="url(#scoreGradient)"
              connectNulls={false}
              dot={(props) => {
                const { cx, cy, payload, index } = props;
                if (cx === undefined || cy === undefined) {
                  return <circle key={`empty-${index}`} r={0} />;
                }
                const data = payload as ChartDataPoint;
                const isSelected =
                  data.year === effectivePeriod.year &&
                  data.month === effectivePeriod.month;

                if (!data.hasData) {
                  return (
                    <circle
                      key={data.key}
                      cx={cx}
                      cy={50}
                      r={isSelected ? 6 : 4}
                      fill="hsl(var(--background))"
                      stroke="hsl(var(--muted-foreground))"
                      strokeWidth={2}
                      strokeDasharray="2 2"
                      className="cursor-pointer"
                    />
                  );
                }

                return (
                  <circle
                    key={data.key}
                    cx={cx}
                    cy={cy}
                    r={isSelected ? 8 : 5}
                    fill={isSelected ? getScoreColor(data.score) : 'hsl(var(--primary))'}
                    stroke={isSelected ? 'hsl(var(--background))' : 'none'}
                    strokeWidth={isSelected ? 3 : 0}
                    className="cursor-pointer transition-all"
                    style={{
                      filter: isSelected ? 'drop-shadow(0 0 4px hsl(var(--primary)))' : 'none',
                    }}
                  />
                );
              }}
              activeDot={{
                r: 8,
                fill: 'hsl(var(--primary))',
                stroke: 'hsl(var(--background))',
                strokeWidth: 3,
                className: 'cursor-pointer',
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Reset button */}
      {selectedPeriod && (
        <div className="flex justify-end mt-1">
          <button
            type="button"
            onClick={() => onPeriodChange(null)}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Reset to latest
          </button>
        </div>
      )}
    </div>
  );
}
