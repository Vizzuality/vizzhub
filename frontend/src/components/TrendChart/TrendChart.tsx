import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { SnapshotWithScores, DimensionScores } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TrendingUp, BarChart3 } from 'lucide-react';

type ChartMode = 'line' | 'bar';

interface TrendChartProps {
  snapshots: SnapshotWithScores[];
  dimensions?: (keyof DimensionScores | 'final_score')[];
  title?: string;
  chartMode?: ChartMode;
  onChartModeChange?: (mode: ChartMode) => void;
  showModeToggle?: boolean;
}

const DIMENSION_COLORS: Record<keyof DimensionScores | 'final_score', string> = {
  p_time: 'oklch(0.7 0.15 220)',
  p_cost: 'oklch(0.7 0.15 140)',
  p_quality: 'oklch(0.7 0.15 30)',
  p_value: 'oklch(0.7 0.15 270)',
  p_satisfaction: 'oklch(0.7 0.15 340)',
  p_flow: 'oklch(0.7 0.15 180)',
  p_engineering: 'oklch(0.7 0.15 60)',
  p_risk: 'oklch(0.7 0.15 310)',
  final_score: 'oklch(0.6726 0.2904 341.4084)',
};

const DIMENSION_LABELS: Record<keyof DimensionScores | 'final_score', string> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk Mgmt',
  final_score: 'Final Score',
};

function formatPeriod(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

export default function TrendChart({
  snapshots,
  dimensions = ['final_score'],
  title = 'Score Trends',
  chartMode = 'line',
  onChartModeChange,
  showModeToggle = false,
}: TrendChartProps): JSX.Element {
  const data = snapshots
    .slice()
    .reverse()
    .map((snapshot) => ({
      period: formatPeriod(snapshot.period_year, snapshot.period_month),
      ...snapshot.scores.dimensions,
      final_score: snapshot.scores.score,
    }));

  const commonAxisProps = {
    tick: { fontSize: 12 },
    tickMargin: 10,
  };

  const tooltipStyle = {
    contentStyle: {
      backgroundColor: 'var(--background)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
    },
    labelStyle: { fontWeight: 'bold' as const },
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>{title}</CardTitle>
        {showModeToggle && onChartModeChange && (
          <div className="flex gap-1">
            <Button
              variant={chartMode === 'line' ? 'default' : 'outline'}
              size="icon"
              className="h-8 w-8"
              onClick={() => onChartModeChange('line')}
              aria-label="Line chart (cumulative trend)"
            >
              <TrendingUp className="h-4 w-4" />
            </Button>
            <Button
              variant={chartMode === 'bar' ? 'default' : 'outline'}
              size="icon"
              className="h-8 w-8"
              onClick={() => onChartModeChange('bar')}
              aria-label="Bar chart (monthly data)"
            >
              <BarChart3 className="h-4 w-4" />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          {chartMode === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="period" {...commonAxisProps} />
              <YAxis domain={[0, 100]} {...commonAxisProps} />
              <Tooltip {...tooltipStyle} />
              <Legend />
              {dimensions.map((dim) => (
                <Line
                  key={dim}
                  type="monotone"
                  dataKey={dim}
                  name={DIMENSION_LABELS[dim]}
                  stroke={DIMENSION_COLORS[dim]}
                  strokeWidth={dim === 'final_score' ? 3 : 2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                  connectNulls
                />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="period" {...commonAxisProps} />
              <YAxis domain={[0, 100]} {...commonAxisProps} />
              <Tooltip {...tooltipStyle} cursor={false} />
              <Legend />
              {dimensions.map((dim) => (
                <Bar
                  key={dim}
                  dataKey={dim}
                  name={DIMENSION_LABELS[dim]}
                  fill={DIMENSION_COLORS[dim]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
