import { useMemo, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { TIMELINE_COLORS } from '../constants';
import type { Period, TimelineDataPoint } from '../types';
import type { GlobalMetricsRecord } from '../../../types/global';
import {
  formatPeriodLabel,
  formatShortPeriod,
  periodKey,
  getTimelineScoreColor,
} from '../utils';

interface TimelineTooltipContentProps {
  readonly active?: boolean;
  readonly payload?: Array<{ payload?: TimelineDataPoint }>;
}

function TimelineTooltipContent({ active, payload }: TimelineTooltipContentProps): JSX.Element | null {
  const data = payload?.[0]?.payload;
  if (!active || !data) return null;
  return (
    <div className="bg-popover border border-border rounded-md px-3 py-2 shadow-md">
      <p className="text-sm font-medium">{formatPeriodLabel(data.year, data.month)}</p>
      {data.hasData ? (
        <p className="text-lg font-bold" style={{ color: getTimelineScoreColor(data.score) }}>
          Score: {Math.round(data.score!)}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">No data calculated</p>
      )}
    </div>
  );
}

interface TimelineDotProps {
  readonly cx?: number;
  readonly cy?: number;
  readonly payload?: TimelineDataPoint;
  readonly index?: number;
  readonly selectedPeriod: Period;
}

function TimelineDot({ cx, cy, payload, index, selectedPeriod }: TimelineDotProps): JSX.Element {
  if (cx === undefined || cy === undefined || !payload) {
    return <circle key={`empty-${index}`} r={0} />;
  }
  const data = payload;
  const isSelected = data.year === selectedPeriod.year && data.month === selectedPeriod.month;

  if (!data.hasData) {
    return (
      <circle
        key={data.key}
        cx={cx}
        cy={50}
        r={isSelected ? 6 : 4}
        fill="transparent"
        stroke={TIMELINE_COLORS.muted}
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
      fill={isSelected ? getTimelineScoreColor(data.score) : TIMELINE_COLORS.primary}
      stroke={isSelected ? '#fff' : 'none'}
      strokeWidth={isSelected ? 3 : 0}
      className="cursor-pointer transition-all"
      style={{
        filter: isSelected ? `drop-shadow(0 0 4px ${TIMELINE_COLORS.primary})` : 'none',
      }}
    />
  );
}

interface GlobalTimelineChartProps {
  readonly periods: Period[];
  readonly history: GlobalMetricsRecord[] | undefined;
  readonly selectedPeriod: Period;
  readonly onPeriodChange: (period: Period) => void;
}

export default function GlobalTimelineChart({
  periods,
  history,
  selectedPeriod,
  onPeriodChange,
}: GlobalTimelineChartProps): JSX.Element {
  const historyMap = useMemo(() => {
    const map = new Map<string, GlobalMetricsRecord>();
    history?.forEach((r) => {
      map.set(periodKey(r.period_year, r.period_month), r);
    });
    return map;
  }, [history]);

  const chartData = useMemo((): TimelineDataPoint[] => {
    return periods.map((p) => {
      const key = periodKey(p.year, p.month);
      const record = historyMap.get(key);
      const score = record?.scores?.score?.value ?? null;
      return {
        key,
        label: formatShortPeriod(p.year, p.month),
        year: p.year,
        month: p.month,
        score,
        hasData: record != null && record.scores.score.count > 0,
      };
    });
  }, [periods, historyMap]);

  const currentScore = useMemo(() => {
    return historyMap.get(periodKey(selectedPeriod.year, selectedPeriod.month))?.scores?.score?.value ?? null;
  }, [selectedPeriod, historyMap]);

  const handleClick = useCallback(
    (data: TimelineDataPoint) => {
      onPeriodChange({ year: data.year, month: data.month });
    },
    [onPeriodChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      const currentIndex = periods.findIndex(
        (p) => p.year === selectedPeriod.year && p.month === selectedPeriod.month,
      );

      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex - 1]);
      } else if (e.key === 'ArrowRight' && currentIndex < periods.length - 1) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex + 1]);
      }
    },
    [periods, selectedPeriod, onPeriodChange],
  );

  const renderDot = useCallback(
    (props: { cx?: number; cy?: number; payload?: TimelineDataPoint; index?: number }): JSX.Element => (
      <TimelineDot
        key={props.payload?.key ?? `dot-${props.index}`}
        cx={props.cx}
        cy={props.cy}
        payload={props.payload}
        index={props.index}
        selectedPeriod={selectedPeriod}
      />
    ),
    [selectedPeriod],
  );

  let tickInterval = 0;
  if (periods.length > 24) {
    tickInterval = 5;
  } else if (periods.length > 12) {
    tickInterval = 2;
  }

  return (
    <div
      className="w-full"
      role="toolbar"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      aria-label="Timeline period selector - use arrow keys to navigate"
      aria-activedescendant={`period-${selectedPeriod.year}-${selectedPeriod.month}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            Timeline
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">
            {formatPeriodLabel(selectedPeriod.year, selectedPeriod.month)}
          </span>
          {currentScore !== null ? (
            <span
              className="text-lg font-bold"
              style={{ color: getTimelineScoreColor(currentScore) }}
            >
              {Math.round(currentScore)}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">No data</span>
          )}
        </div>
      </div>

      {/* Chart range info */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="text-sm text-muted-foreground">
          {formatPeriodLabel(periods[0].year, periods[0].month)} — {formatPeriodLabel(periods[periods.length - 1].year, periods[periods.length - 1].month)}
        </div>
      </div>

      {/* Chart */}
      <div className="h-24 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            onClick={(e) => {
              if (e?.activePayload?.[0]?.payload) {
                handleClick(e.activePayload[0].payload as TimelineDataPoint);
              }
            }}
          >
            <defs>
              <linearGradient id="globalScoreGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={TIMELINE_COLORS.primary} stopOpacity={0.3} />
                <stop offset="95%" stopColor={TIMELINE_COLORS.primary} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fill: TIMELINE_COLORS.muted }}
              interval={tickInterval}
            />
            <YAxis domain={[0, 100]} hide />
            <RechartsTooltip content={TimelineTooltipContent} />
            <ReferenceLine
              x={formatShortPeriod(selectedPeriod.year, selectedPeriod.month)}
              stroke={TIMELINE_COLORS.primary}
              strokeWidth={2}
              strokeDasharray="3 3"
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke={TIMELINE_COLORS.primary}
              strokeWidth={2}
              fill="url(#globalScoreGradient)"
              connectNulls={false}
              dot={renderDot}
              activeDot={{
                r: 8,
                fill: TIMELINE_COLORS.primary,
                stroke: '#fff',
                strokeWidth: 3,
                className: 'cursor-pointer',
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
