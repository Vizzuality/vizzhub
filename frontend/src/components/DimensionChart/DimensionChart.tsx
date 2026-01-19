import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { DimensionScores } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface DimensionChartProps {
  scores: DimensionScores;
}

const DIMENSION_LABELS: Record<keyof DimensionScores, string> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk',
};

export default function DimensionChart({ scores }: DimensionChartProps): JSX.Element {
  const data = Object.entries(scores).map(([key, value]) => ({
    dimension: DIMENSION_LABELS[key as keyof DimensionScores],
    score: value,
    fullMark: 100,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dimension Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Score"
            dataKey="score"
            stroke="hsl(346.8 77.2% 49.8%)"
            fill="hsl(346.8 77.2% 49.8%)"
            fillOpacity={0.5}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload as { dimension: string; score: number };
                return (
                  <div className="bg-background shadow-lg rounded-lg p-2 border">
                    <p className="font-medium">{item.dimension}</p>
                    <p className="text-primary">{item.score}/100</p>
                  </div>
                );
              }
              return null;
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
