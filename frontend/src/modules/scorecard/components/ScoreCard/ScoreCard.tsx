import { useState } from 'react';
import { TrendingUp, Maximize2, Minimize2, RotateCcw } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { FinalScore, MetricsWithScores, Dimension } from '../../types';
import { formatPeriod } from '@/utils/formatters';
import { CHART_TOOLTIP_STYLE } from '@/utils/chartUtils';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useScoreThresholds } from '@/modules/scorecard/hooks/useConfig';
import { getScoreBgColor, getScoreDotClass } from '@/utils/scoreColors';

interface ScoreCardProps {
  readonly score: FinalScore;
  readonly title?: string;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
  readonly onToggleDimension?: (dimension: Dimension) => void;
  readonly onResetFilters?: () => void;
}

export default function ScoreCard({
  score,
  title = 'Overall Score',
  snapshots,
  visibleDimensions,
  onToggleDimension,
  onResetFilters,
}: ScoreCardProps): JSX.Element {
  const thresholds = useScoreThresholds();
  const [showChart, setShowChart] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const hasFilters = visibleDimensions && visibleDimensions.size < 8;

  const chartData = snapshots && snapshots.length > 1
    ? snapshots
        .slice()
        .reverse()
        .map((s) => ({
          period: formatPeriod(s.period_year, s.period_month),
          score: s.scores?.score ?? 0,
        }))
    : [];

  const hasChartData = chartData.length > 1;
  const displayData = chartData.slice(-6);

  const renderChart = (data: typeof chartData, height: number) => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
        <XAxis dataKey="period" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
        <Line
          type="monotone"
          dataKey="score"
          stroke="var(--primary)"
          strokeWidth={2}
          dot={{ fill: 'var(--primary)', r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        {hasChartData && (
          <div className="flex gap-1">
            <TooltipProvider>
              <UITooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => {
                      setShowChart(!showChart);
                      if (showChart) setExpanded(false);
                    }}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showChart
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    )}
                  >
                    <TrendingUp className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Historical trend</p>
                </TooltipContent>
              </UITooltip>
            </TooltipProvider>
            {showChart && (
              <TooltipProvider>
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => setExpanded(!expanded)}
                      className={cn(
                        'p-1.5 rounded-md transition-colors',
                        expanded
                          ? 'bg-primary/20 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      )}
                    >
                      {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">{expanded ? 'Collapse' : 'Expand'}</p>
                  </TooltipContent>
                </UITooltip>
              </TooltipProvider>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent>
        {showChart && hasChartData ? (
          <div className="mb-4">
            <div className="w-full h-48">
              {renderChart(displayData, 192)}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center mb-6">
            <div
              className={`w-32 h-32 rounded-full flex items-center justify-center ${getScoreBgColor(score.score, thresholds)}`}
            >
              <span className="text-5xl font-semibold text-foreground flex items-center gap-2">
                <span className={cn('inline-block w-3 h-3 rounded-full shrink-0', getScoreDotClass(score.score, thresholds))} />
                {score.score ?? '—'}
              </span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <DimensionBadge label="Time" dimension="Time" score={score.dimensions.p_time} thresholds={thresholds} isVisible={visibleDimensions?.has('Time') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Cost" dimension="Cost" score={score.dimensions.p_cost} thresholds={thresholds} isVisible={visibleDimensions?.has('Cost') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Quality" dimension="Quality" score={score.dimensions.p_quality} thresholds={thresholds} isVisible={visibleDimensions?.has('Quality') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Value" dimension="Value" score={score.dimensions.p_value} thresholds={thresholds} isVisible={visibleDimensions?.has('Value') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Satisfaction" dimension="Satisfaction" score={score.dimensions.p_satisfaction} thresholds={thresholds} isVisible={visibleDimensions?.has('Satisfaction') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Flow" dimension="Flow" score={score.dimensions.p_flow} thresholds={thresholds} isVisible={visibleDimensions?.has('Flow') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Engineering" dimension="Engineering" score={score.dimensions.p_engineering} thresholds={thresholds} isVisible={visibleDimensions?.has('Engineering') ?? true} onToggle={onToggleDimension} />
          <DimensionBadge label="Risk Mgmt" dimension="Risk" score={score.dimensions.p_risk} thresholds={thresholds} isVisible={visibleDimensions?.has('Risk') ?? true} onToggle={onToggleDimension} />
        </div>
        {hasFilters && onResetFilters && (
          <button
            type="button"
            onClick={onResetFilters}
            className="mt-3 flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors mx-auto"
          >
            <RotateCcw className="h-3 w-3" />
            Reset filters
          </button>
        )}
      </CardContent>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{title} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-96">
            {renderChart(chartData, 384)}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

interface DimensionBadgeProps {
  readonly label: string;
  readonly dimension: Dimension;
  readonly score: number | null;
  readonly thresholds: { green: number; yellow: number };
  readonly isVisible: boolean;
  readonly onToggle?: (dimension: Dimension) => void;
}

function DimensionBadge({ label, dimension, score, thresholds, isVisible, onToggle }: DimensionBadgeProps): JSX.Element {
  const isClickable = !!onToggle;

  const content = (
    <>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'w-2.5 h-2.5 rounded-full border-2 transition-colors',
            isVisible
              ? 'bg-primary border-primary'
              : 'bg-transparent border-muted-foreground/50'
          )}
        />
        <span className={cn(
          'text-base transition-colors',
          isVisible ? 'text-foreground' : 'text-muted-foreground'
        )}>
          {label}
        </span>
      </div>
      <span className={cn(
        'text-lg font-medium transition-opacity flex items-center gap-1.5',
        isVisible ? 'text-foreground' : 'text-muted-foreground'
      )}>
        {score !== null && (
          <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', isVisible ? getScoreDotClass(score, thresholds) : 'bg-muted-foreground/50')} />
        )}
        {score ?? '—'}
      </span>
    </>
  );

  const baseClassName = cn(
    'flex items-center justify-between p-3 rounded-lg transition-all w-full',
    isVisible ? 'bg-muted' : 'bg-muted/30 opacity-50'
  );

  if (isClickable) {
    return (
      <button
        type="button"
        onClick={() => onToggle(dimension)}
        className={baseClassName}
      >
        {content}
      </button>
    );
  }

  return <div className={baseClassName}>{content}</div>;
}
