import { useMemo } from 'react';
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
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { cn } from '@/lib/utils';
import { getScoreColor, getScoreBgColor } from '@/utils/scoreColors';
import { formatPeriod } from '@/utils/formatters';
import { CHART_TOOLTIP_STYLE } from '@/utils/chartUtils';
import { useTrendExpand } from '../../../hooks/useTrendExpand';
import type { Dimension } from '../../../types';
import type { GlobalMetricsRecord } from '../../../types/global';
import GlobalDimensionBadge from './GlobalDimensionBadge';

interface GlobalScoreCardProps {
  readonly metrics: GlobalMetricsRecord;
  readonly thresholds: { green: number; yellow: number };
  readonly history?: GlobalMetricsRecord[];
  readonly visibleDimensions: Set<Dimension>;
  readonly onToggleDimension: (dimension: Dimension) => void;
}

export default function GlobalScoreCard({
  metrics,
  thresholds,
  history,
  visibleDimensions,
  onToggleDimension,
}: GlobalScoreCardProps): JSX.Element {
  const { showTrend: showChart, expanded, toggleTrend, toggleExpand, setExpanded } = useTrendExpand();

  const hasData = metrics.scores.score.value !== null && metrics.scores.score.count > 0;
  const displayScore = hasData ? Math.round(metrics.scores.score.value!) : null;

  const chartData = useMemo(() => {
    if (!history || history.length < 2) return [];
    return history
      .slice()
      .reverse()
      .filter((r) => r.scores.score.value !== null && r.scores.score.count > 0)
      .map((r) => ({
        period: formatPeriod(r.period_year, r.period_month),
        score: Math.round(r.scores.score.value!),
      }));
  }, [history]);

  const hasChartData = chartData.length > 1;
  const displayData = chartData.slice(-6);

  const renderChart = (data: typeof chartData, height: number): JSX.Element => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
        <XAxis dataKey="period" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
        <RechartsTooltip contentStyle={CHART_TOOLTIP_STYLE} />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ fill: '#3b82f6', r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Overall Score</CardTitle>
        {hasChartData && (
          <div className="flex gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={toggleTrend}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showChart
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
            {showChart && (
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
        {showChart && hasChartData ? (
          <div className="mb-4">
            <div className="w-full h-48">{renderChart(displayData, 192)}</div>
          </div>
        ) : (
          <div className="flex items-center justify-center mb-6">
            <div
              className={cn(
                'w-32 h-32 rounded-full flex items-center justify-center',
                hasData ? getScoreBgColor(displayScore, thresholds) : 'bg-muted',
              )}
            >
              <span
                className={cn(
                  'text-5xl font-semibold',
                  hasData ? getScoreColor(displayScore, thresholds) : 'text-muted-foreground',
                )}
              >
                {displayScore ?? '—'}
              </span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <GlobalDimensionBadge label="Time" dimension="Time" score={metrics.scores.p_time} thresholds={thresholds} isVisible={visibleDimensions.has('Time')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Cost" dimension="Cost" score={metrics.scores.p_cost} thresholds={thresholds} isVisible={visibleDimensions.has('Cost')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Quality" dimension="Quality" score={metrics.scores.p_quality} thresholds={thresholds} isVisible={visibleDimensions.has('Quality')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Value" dimension="Value" score={metrics.scores.p_value} thresholds={thresholds} isVisible={visibleDimensions.has('Value')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Satisfaction" dimension="Satisfaction" score={metrics.scores.p_satisfaction} thresholds={thresholds} isVisible={visibleDimensions.has('Satisfaction')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Flow" dimension="Flow" score={metrics.scores.p_flow} thresholds={thresholds} isVisible={visibleDimensions.has('Flow')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Engineering" dimension="Engineering" score={metrics.scores.p_engineering} thresholds={thresholds} isVisible={visibleDimensions.has('Engineering')} onToggle={onToggleDimension} />
          <GlobalDimensionBadge label="Risk Mgmt" dimension="Risk" score={metrics.scores.p_risk} thresholds={thresholds} isVisible={visibleDimensions.has('Risk')} onToggle={onToggleDimension} />
        </div>
      </CardContent>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Overall Score - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-96">{renderChart(chartData, 384)}</div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
