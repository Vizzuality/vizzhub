import { useMemo, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { TrendingUp, Maximize2, Minimize2 } from 'lucide-react';
import {
  LineChart,
  Line,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { cn } from '@/lib/utils';
import { formatPeriod } from '@/utils/formatters';
import { CHART_TOOLTIP_STYLE } from '@/utils/chartUtils';
import { useTrendExpand } from '../../../hooks/useTrendExpand';
import type { Dimension } from '../../../types';
import type { GlobalMetricsRecord } from '../../../types/global';
import {
  DIMENSION_KEYS,
  DIMENSION_KEY_LABELS,
  DIMENSION_KEY_COLORS,
  KEY_TO_DIMENSION,
  type DimensionKey,
} from '../constants';

interface RadarTooltipPayload {
  dimension: string;
  score: number;
  isNeutral: boolean;
}

interface RadarTooltipProps {
  active?: boolean;
  payload?: Array<{ payload?: RadarTooltipPayload }>;
}

function GlobalRadarTooltipContent({ active, payload }: RadarTooltipProps): JSX.Element | null {
  const item = payload?.[0]?.payload;
  if (!active || !item) return null;
  return (
    <div className="bg-background shadow-lg rounded-lg p-2 border">
      <p className="font-medium">{item.dimension}</p>
      {item.isNeutral ? (
        <p className="text-muted-foreground">No data</p>
      ) : (
        <p className="text-primary">{item.score}/100</p>
      )}
    </div>
  );
}

interface DimensionBreakdownChartProps {
  readonly metrics: GlobalMetricsRecord;
  readonly history?: GlobalMetricsRecord[];
  readonly visibleDimensions: Set<Dimension>;
  readonly onToggleDimension: (dimension: Dimension) => void;
}

export default function DimensionBreakdownChart({
  metrics,
  history,
  visibleDimensions,
  onToggleDimension,
}: DimensionBreakdownChartProps): JSX.Element {
  const { showTrend, expanded, toggleTrend, toggleExpand, setExpanded } = useTrendExpand();

  const isVisible = (key: DimensionKey): boolean => visibleDimensions.has(KEY_TO_DIMENSION[key]);
  const visibleKeys = DIMENSION_KEYS.filter(isVisible);

  const radarData = useMemo(() => {
    return DIMENSION_KEYS.map((key) => {
      const scoreValue = metrics.scores[key];
      const value = scoreValue?.value;
      return {
        dimension: DIMENSION_KEY_LABELS[key],
        score: value !== null ? Math.round(value) : 0,
        isNeutral: value === null || scoreValue.count === 0,
        fullMark: 100,
      };
    });
  }, [metrics]);

  const trendData = useMemo(() => {
    if (!history || history.length < 2) return [];
    return history
      .slice()
      .reverse()
      .map((r) => ({
        period: formatPeriod(r.period_year, r.period_month),
        p_time: r.scores.p_time.value !== null ? Math.round(r.scores.p_time.value) : 0,
        p_cost: r.scores.p_cost.value !== null ? Math.round(r.scores.p_cost.value) : 0,
        p_quality: r.scores.p_quality.value !== null ? Math.round(r.scores.p_quality.value) : 0,
        p_value: r.scores.p_value.value !== null ? Math.round(r.scores.p_value.value) : 0,
        p_satisfaction: r.scores.p_satisfaction.value !== null ? Math.round(r.scores.p_satisfaction.value) : 0,
        p_flow: r.scores.p_flow.value !== null ? Math.round(r.scores.p_flow.value) : 0,
        p_engineering: r.scores.p_engineering.value !== null ? Math.round(r.scores.p_engineering.value) : 0,
        p_risk: r.scores.p_risk.value !== null ? Math.round(r.scores.p_risk.value) : 0,
      }));
  }, [history]);

  const hasChartData = trendData.length > 1;
  const displayData = trendData.slice(-6);

  const primaryColor =
    typeof window !== 'undefined'
      ? getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()
      : 'oklch(0.6726 0.2904 341.4084)';

  const customLegend = useCallback(() => {
    return (
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 mt-2">
        {DIMENSION_KEYS.map((key) => {
          const visible = visibleDimensions.has(KEY_TO_DIMENSION[key]);
          const dimension = KEY_TO_DIMENSION[key];
          return (
            <button
              key={key}
              onClick={() => onToggleDimension(dimension)}
              className={cn(
                'flex items-center gap-1.5 text-[10px] transition-opacity cursor-pointer hover:opacity-80',
                !visible && 'opacity-40',
              )}
            >
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: visible ? DIMENSION_KEY_COLORS[key] : '#9ca3af' }}
              />
              <span className={cn(!visible && 'line-through')}>{DIMENSION_KEY_LABELS[key]}</span>
            </button>
          );
        })}
      </div>
    );
  }, [visibleDimensions, onToggleDimension]);

  const renderTrendChart = (data: typeof trendData, height: number): JSX.Element => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
        <XAxis dataKey="period" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
        <RechartsTooltip contentStyle={{ ...CHART_TOOLTIP_STYLE, fontSize: '11px' }} />
        <Legend content={customLegend} />
        {visibleKeys.map((key) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={DIMENSION_KEY_LABELS[key]}
            stroke={DIMENSION_KEY_COLORS[key]}
            strokeWidth={1.5}
            dot={{ r: 2 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Dimension Breakdown</CardTitle>
        {hasChartData && (
          <div className="flex gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={toggleTrend}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showTrend
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted',
                    )}
                  >
                    <TrendingUp className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Historical trend</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {showTrend && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={toggleExpand}
                      className={cn(
                        'p-1.5 rounded-md transition-colors',
                        expanded
                          ? 'bg-primary/20 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted',
                      )}
                    >
                      {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">{expanded ? 'Collapse' : 'Expand'}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent>
        {showTrend && hasChartData ? (
          <div className="w-full h-[350px]">{renderTrendChart(displayData, 350)}</div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 14 }} tickSize={20} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Radar name="Score" dataKey="score" stroke={primaryColor} fill={primaryColor} fillOpacity={0.5} />
              <RechartsTooltip content={GlobalRadarTooltipContent} />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </CardContent>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Dimension Breakdown - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-[450px]">{renderTrendChart(trendData, 450)}</div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
