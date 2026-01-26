import type { FinalScore } from '../../types';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface ScoreCardProps {
  score: FinalScore;
  title?: string;
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground';
  if (score >= 80) return 'text-green-600 dark:text-green-400';
  if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function getScoreBgColor(score: number | null): string {
  if (score === null) return 'bg-muted';
  if (score >= 80) return 'bg-green-600/20 dark:bg-green-400/20';
  if (score >= 60) return 'bg-yellow-600/20 dark:bg-yellow-400/20';
  return 'bg-red-600/20 dark:bg-red-400/20';
}

export default function ScoreCard({ score, title = 'Overall Score' }: ScoreCardProps): JSX.Element {
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
          <DimensionBadge label="Time" score={score.dimensions.p_time} />
          <DimensionBadge label="Cost" score={score.dimensions.p_cost} />
          <DimensionBadge label="Quality" score={score.dimensions.p_quality} />
          <DimensionBadge label="Value" score={score.dimensions.p_value} />
          <DimensionBadge label="Satisfaction" score={score.dimensions.p_satisfaction} />
          <DimensionBadge label="Flow" score={score.dimensions.p_flow} />
          <DimensionBadge label="Engineering" score={score.dimensions.p_engineering} />
          <DimensionBadge label="Risk Mgmt" score={score.dimensions.p_risk} />
        </div>
      </CardContent>
    </Card>
  );
}

interface DimensionBadgeProps {
  label: string;
  score: number | null;
}

function DimensionBadge({ label, score }: DimensionBadgeProps): JSX.Element {
  return (
    <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
      <span className="text-base text-muted-foreground">{label}</span>
      <span className={`text-lg font-medium ${getScoreColor(score)}`}>
        {score !== null ? score : '—'}
      </span>
    </div>
  );
}
