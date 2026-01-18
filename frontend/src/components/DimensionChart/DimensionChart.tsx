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
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">Dimension Breakdown</h3>
      <ResponsiveContainer width="100%" height={350}>
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#2563eb"
            fill="#3b82f6"
            fillOpacity={0.5}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload as { dimension: string; score: number };
                return (
                  <div className="bg-white shadow-lg rounded-lg p-2 border">
                    <p className="font-medium">{item.dimension}</p>
                    <p className="text-primary-600">{item.score}/100</p>
                  </div>
                );
              }
              return null;
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
