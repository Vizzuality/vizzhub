import { useState } from 'react';
import { TrendingUp, BarChart3, Maximize2, Minimize2 } from 'lucide-react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { DimensionScores, MetricsWithScores } from '../../types';
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

interface DimensionChartProps {
  scores: DimensionScores;
  snapshots?: MetricsWithScores[];
}

const DIMENSION_LABELS: Record<keyof DimensionScores, string> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk Mgmt',
};

const NEUTRAL_SCORE = 0;

const DIMENSION_COLORS: Record<keyof DimensionScores, string> = {
  p_time: '#3b82f6',
  p_cost: '#10b981',
  p_quality: '#f59e0b',
  p_value: '#8b5cf6',
  p_satisfaction: '#ec4899',
  p_flow: '#06b6d4',
  p_engineering: '#f97316',
  p_risk: '#ef4444',
};

function formatPeriod(year: number, month: number): string {
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[month - 1]} ${year.toString().slice(-2)}`;
}

export default function DimensionChart({ scores, snapshots }: DimensionChartProps): JSX.Element {
  const [showTrend, setShowTrend] = useState(false);
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line');
  const [expanded, setExpanded] = useState(false);

  const radarData = Object.entries(scores).map(([key, value]) => ({
    dimension: DIMENSION_LABELS[key as keyof DimensionScores],
    score: value ?? NEUTRAL_SCORE,
    isNeutral: value === null,
    fullMark: 100,
  }));

  const trendData = snapshots && snapshots.length > 1
    ? snapshots
        .slice()
        .reverse()
        .map((s) => ({
          period: formatPeriod(s.period_year, s.period_month),
          ...Object.fromEntries(
            Object.entries(s.scores.dimensions).map(([key, value]) => [key, value ?? 0])
          ),
        }))
    : [];

  const hasChartData = trendData.length > 1;
  const displayData = trendData.slice(-6);

  // Get primary color from CSS variable
  const primaryColor = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()
    : 'oklch(0.6726 0.2904 341.4084)';

  const renderTrendChart = (data: typeof trendData, height: number) => (
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
              fontSize: '11px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '10px' }} />
          {(Object.keys(DIMENSION_LABELS) as (keyof DimensionScores)[]).map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={DIMENSION_LABELS[key]}
              stroke={DIMENSION_COLORS[key]}
              strokeWidth={1.5}
              dot={{ r: 2 }}
            />
          ))}
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
              fontSize: '11px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '10px' }} />
          {(Object.keys(DIMENSION_LABELS) as (keyof DimensionScores)[]).map((key) => (
            <Bar
              key={key}
              dataKey={key}
              name={DIMENSION_LABELS[key]}
              fill={DIMENSION_COLORS[key]}
              radius={[2, 2, 0, 0]}
            />
          ))}
        </BarChart>
      )}
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Dimension Breakdown</CardTitle>
        {hasChartData && (
          <div className="flex gap-1">
            <TooltipProvider>
              <UITooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => {
                      if (showTrend && chartMode === 'line') {
                        setShowTrend(false);
                        setExpanded(false);
                      } else {
                        setShowTrend(true);
                        setChartMode('line');
                      }
                    }}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showTrend && chartMode === 'line'
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
                      if (showTrend && chartMode === 'bar') {
                        setShowTrend(false);
                        setExpanded(false);
                      } else {
                        setShowTrend(true);
                        setChartMode('bar');
                      }
                    }}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showTrend && chartMode === 'bar'
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
            {showTrend && (
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
        {showTrend && hasChartData ? (
          <div className="w-full h-[350px]">
            {renderTrendChart(displayData, 350)}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 14 }} tickSize={20} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Radar
                name="Score"
                dataKey="score"
                stroke={primaryColor}
                fill={primaryColor}
                fillOpacity={0.5}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload as { dimension: string; score: number; isNeutral: boolean };
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
                  return null;
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </CardContent>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Dimension Breakdown - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-[450px]">
            {renderTrendChart(trendData, 450)}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
