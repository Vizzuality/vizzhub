import { useState } from 'react';
import { TrendingUp, BarChart3, Maximize2, Minimize2 } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { FinalScore, MetricsWithScores } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useScoreThresholds } from '@/hooks/useConfig';
import { getScoreColor, getScoreBgColor } from '@/utils/scoreColors';

interface ScoreCardProps {
  score: FinalScore;
  title?: string;
  snapshots?: MetricsWithScores[];
}

function formatPeriod(year: number, month: number): string {
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[month - 1]} ${year.toString().slice(-2)}`;
}

export default function ScoreCard({ score, title = 'Overall Score', snapshots }: ScoreCardProps): JSX.Element {
  const thresholds = useScoreThresholds();
  const [showChart, setShowChart] = useState(false);
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line');
  const [expanded, setExpanded] = useState(false);

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
      {chartMode === 'line' ? (
        <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
          <XAxis dataKey="period" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
              fontSize: '12px',
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ fill: '#3b82f6', r: 4 }}
          />
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
          <XAxis dataKey="period" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip
            cursor={false}
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '6px',
              fontSize: '12px',
            }}
          />
          <Bar dataKey="score" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      )}
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
                    onClick={() => {
                      if (showChart && chartMode === 'line') {
                        setShowChart(false);
                        setExpanded(false);
                      } else {
                        setShowChart(true);
                        setChartMode('line');
                      }
                    }}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showChart && chartMode === 'line'
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    )}
                  >
                    <TrendingUp className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Cumulative trend</p>
                </TooltipContent>
              </UITooltip>
            </TooltipProvider>
            <TooltipProvider>
              <UITooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => {
                      if (showChart && chartMode === 'bar') {
                        setShowChart(false);
                        setExpanded(false);
                      } else {
                        setShowChart(true);
                        setChartMode('bar');
                      }
                    }}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showChart && chartMode === 'bar'
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    )}
                  >
                    <BarChart3 className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Monthly data</p>
                </TooltipContent>
              </UITooltip>
            </TooltipProvider>
            {showChart && (
              <TooltipProvider>
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button
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
              <span className={`text-5xl font-semibold ${getScoreColor(score.score, thresholds)}`}>
                {score.score}
              </span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <DimensionBadge label="Time" score={score.dimensions.p_time} thresholds={thresholds} />
          <DimensionBadge label="Cost" score={score.dimensions.p_cost} thresholds={thresholds} />
          <DimensionBadge label="Quality" score={score.dimensions.p_quality} thresholds={thresholds} />
          <DimensionBadge label="Value" score={score.dimensions.p_value} thresholds={thresholds} />
          <DimensionBadge label="Satisfaction" score={score.dimensions.p_satisfaction} thresholds={thresholds} />
          <DimensionBadge label="Flow" score={score.dimensions.p_flow} thresholds={thresholds} />
          <DimensionBadge label="Engineering" score={score.dimensions.p_engineering} thresholds={thresholds} />
          <DimensionBadge label="Risk Mgmt" score={score.dimensions.p_risk} thresholds={thresholds} />
        </div>
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
  label: string;
  score: number | null;
  thresholds: { green: number; yellow: number };
}

function DimensionBadge({ label, score, thresholds }: DimensionBadgeProps): JSX.Element {
  return (
    <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
      <span className="text-base text-muted-foreground">{label}</span>
      <span className={`text-lg font-medium ${getScoreColor(score, thresholds)}`}>
        {score !== null ? score : '—'}
      </span>
    </div>
  );
}
