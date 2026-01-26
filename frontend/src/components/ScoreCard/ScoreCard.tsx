import type { FinalScore } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { useScoreThresholds } from '@/hooks/useConfig';

interface ScoreCardProps {
  score: FinalScore;
  title?: string;
}

export default function ScoreCard({ score, title = 'Overall Score' }: ScoreCardProps): JSX.Element {
  const thresholds = useScoreThresholds();

  const getScoreColor = (value: number | null): string => {
    if (value === null) return 'text-muted-foreground';
    if (value >= thresholds.green) return 'text-score-green';
    if (value >= thresholds.yellow) return 'text-score-yellow';
    return 'text-score-red';
  };

  const getScoreBgColor = (value: number | null): string => {
    if (value === null) return 'bg-muted';
    if (value >= thresholds.green) return 'bg-score-green-bg';
    if (value >= thresholds.yellow) return 'bg-score-yellow-bg';
    return 'bg-score-red-bg';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>

      <CardContent>
        <div className="flex items-center justify-center mb-6">
          <div
            className={`w-32 h-32 rounded-full flex items-center justify-center ${getScoreBgColor(score.score)}`}
          >
            <span className={`text-5xl font-semibold ${getScoreColor(score.score)}`}>
              {score.score}
            </span>
          </div>
        </div>

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
    </Card>
  );
}

interface DimensionBadgeProps {
  label: string;
  score: number | null;
  thresholds: { green: number; yellow: number };
}

function DimensionBadge({ label, score, thresholds }: DimensionBadgeProps): JSX.Element {
  const getScoreColor = (value: number | null): string => {
    if (value === null) return 'text-muted-foreground';
    if (value >= thresholds.green) return 'text-score-green';
    if (value >= thresholds.yellow) return 'text-score-yellow';
    return 'text-score-red';
  };

  return (
    <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
      <span className="text-base text-muted-foreground">{label}</span>
      <span className={`text-lg font-medium ${getScoreColor(score)}`}>
        {score !== null ? score : '—'}
      </span>
    </div>
  );
}
