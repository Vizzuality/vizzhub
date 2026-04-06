import { useMemo, useCallback, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  TIMELINE_CHART_COLORS,
  getScoreColor,
  getTickInterval,
} from '@/shared/components/ui/timeline-chart';
import type { MetricsWithScores } from '../../types';
import {
  formatPeriod,
  formatShortPeriod,
  generateMonthRange,
  periodKey,
  type Period,
} from '@/utils/dateUtils';

interface InteractiveTimelineChartProps {
  readonly projectStartDate: string;
  readonly projectFinishedAt?: string | null;
  readonly snapshots: MetricsWithScores[] | undefined;
  readonly selectedPeriod: Period | null;
  readonly onPeriodChange: (period: Period | null) => void;
  readonly isCapturing?: boolean;
  readonly onCollectMetrics?: (period: Period, force: boolean) => Promise<void>;
  readonly isCollecting?: boolean;
  readonly hasCollectors?: boolean;
  readonly isFinished?: boolean;
}

interface ChartDataPoint {
  readonly key: string;
  readonly label: string;
  readonly year: number;
  readonly month: number;
  readonly score: number | null;
  readonly hasData: boolean;
}

interface ChartTooltipContentProps {
  readonly active?: boolean;
  readonly payload?: Array<{ payload?: ChartDataPoint }>;
}

function ChartTooltipContent({ active, payload }: ChartTooltipContentProps): JSX.Element | null {
  const data = payload?.[0]?.payload;
  if (!active || !data) return null;
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
}

interface ChartDotProps {
  readonly cx?: number;
  readonly cy?: number;
  readonly payload?: ChartDataPoint;
  readonly index?: number;
  readonly effectivePeriod: Period;
}

function ChartDot({ cx, cy, payload, index, effectivePeriod }: ChartDotProps): JSX.Element {
  if (cx === undefined || cy === undefined || !payload) {
    return <circle key={`empty-${index}`} r={0} />;
  }
  const data = payload;
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
        fill="transparent"
        stroke={TIMELINE_CHART_COLORS.muted}
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
      fill={isSelected ? getScoreColor(data.score) : TIMELINE_CHART_COLORS.primary}
      stroke={isSelected ? '#fff' : 'none'}
      strokeWidth={isSelected ? 3 : 0}
      className="cursor-pointer transition-all"
      style={{
        filter: isSelected ? `drop-shadow(0 0 4px ${TIMELINE_CHART_COLORS.primary})` : 'none',
      }}
    />
  );
}

export default function InteractiveTimelineChart({
  projectStartDate,
  projectFinishedAt,
  snapshots,
  selectedPeriod,
  onPeriodChange,
  isCapturing = false,
  onCollectMetrics,
  isCollecting = false,
  hasCollectors = false,
  isFinished = false,
}: InteractiveTimelineChartProps): JSX.Element {
  const [showCollectDialog, setShowCollectDialog] = useState(false);

  const periods = useMemo(
    () => generateMonthRange(projectStartDate, projectFinishedAt),
    [projectStartDate, projectFinishedAt],
  );

  const snapshotMap = useMemo(() => {
    const map = new Map<string, MetricsWithScores>();
    snapshots?.forEach((s) => {
      map.set(periodKey(s.period_year, s.period_month), s);
    });
    return map;
  }, [snapshots]);

  const chartData = useMemo((): ChartDataPoint[] => {
    return periods.map((p) => {
      const key = periodKey(p.year, p.month);
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
      if (snapshotMap.has(periodKey(p.year, p.month))) {
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
    return snapshotMap.get(periodKey(effectivePeriod.year, effectivePeriod.month))?.scores?.score ?? null;
  }, [effectivePeriod, snapshotMap]);

  const periodHasData = useMemo(() => {
    return snapshotMap.has(periodKey(effectivePeriod.year, effectivePeriod.month));
  }, [effectivePeriod, snapshotMap]);

  const handleCollectClick = useCallback(() => {
    if (periodHasData) {
      setShowCollectDialog(true);
    } else if (onCollectMetrics) {
      onCollectMetrics(effectivePeriod, false);
    }
  }, [periodHasData, effectivePeriod, onCollectMetrics]);

  const handleConfirmCollect = useCallback(async () => {
    setShowCollectDialog(false);
    if (onCollectMetrics) {
      await onCollectMetrics(effectivePeriod, true);
    }
  }, [effectivePeriod, onCollectMetrics]);

  const renderDot = useCallback(
    (props: { cx?: number; cy?: number; payload?: ChartDataPoint; index?: number }): JSX.Element => (
      <ChartDot
        cx={props.cx}
        cy={props.cy}
        payload={props.payload}
        index={props.index}
        effectivePeriod={effectivePeriod}
      />
    ),
    [effectivePeriod],
  );

  const tickInterval = getTickInterval(periods.length);

  return (
    <>
      {/* Collect Confirmation Dialog */}
      <AlertDialog open={showCollectDialog} onOpenChange={setShowCollectDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Overwrite metrics?</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to overwrite the metrics for{' '}
              <strong>{formatPeriod(effectivePeriod.year, effectivePeriod.month)}</strong>.
              This will replace all collected data (Jira & GitHub) for this period.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmCollect}>
              Overwrite
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div
        className="w-full"
        role="toolbar"
        onKeyDown={handleKeyDown}
        tabIndex={0}
        aria-label="Timeline period selector - use arrow keys to navigate"
        aria-activedescendant={`period-${effectivePeriod.year}-${effectivePeriod.month}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <h2 className="text-2xl font-semibold">Scores</h2>
            {hasCollectors && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleCollectClick}
                disabled={isCollecting || isCapturing || isFinished}
              >
                <RefreshCw
                  className={cn('w-4 h-4 mr-2', (isCollecting || isCapturing) && 'animate-spin')}
                />
                {isCollecting || isCapturing ? 'Collecting...' : 'Collect Metrics'}
              </Button>
            )}
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

        {/* Chart info row */}
        <div className="flex items-center justify-between mb-2 px-1">
          <div className="text-sm text-muted-foreground">
            {formatPeriod(periods[0].year, periods[0].month)} — {formatPeriod(periods[periods.length - 1].year, periods[periods.length - 1].month)}
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
                <stop offset="5%" stopColor={TIMELINE_CHART_COLORS.primary} stopOpacity={0.3} />
                <stop offset="95%" stopColor={TIMELINE_CHART_COLORS.primary} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: TIMELINE_CHART_COLORS.muted }}
              interval={tickInterval}
            />
            <YAxis
              domain={[0, 100]}
              hide
            />
            <Tooltip content={ChartTooltipContent} />
            <ReferenceLine
              x={formatShortPeriod(effectivePeriod.year, effectivePeriod.month)}
              stroke={TIMELINE_CHART_COLORS.primary}
              strokeWidth={2}
              strokeDasharray="3 3"
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke={TIMELINE_CHART_COLORS.primary}
              strokeWidth={2}
              fill="url(#scoreGradient)"
              connectNulls={false}
              dot={renderDot}
              activeDot={{
                r: 8,
                fill: TIMELINE_CHART_COLORS.primary,
                stroke: '#fff',
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
    </>
  );
}
