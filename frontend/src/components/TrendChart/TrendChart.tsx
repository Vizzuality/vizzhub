import {
  LineChart,
  Line,
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

interface TrendChartProps {
  snapshots: SnapshotWithScores[];
  dimensions?: (keyof DimensionScores | 'final_score')[];
  title?: string;
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
}: TrendChartProps): JSX.Element {
  const data = snapshots
    .slice()
    .reverse()
    .map((snapshot) => ({
      period: formatPeriod(snapshot.period_year, snapshot.period_month),
      ...snapshot.scores.dimensions,
      final_score: snapshot.scores.score,
    }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="period"
              tick={{ fontSize: 12 }}
              tickMargin={10}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 12 }}
              tickMargin={10}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--background)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
              }}
              labelStyle={{ fontWeight: 'bold' }}
            />
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
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
