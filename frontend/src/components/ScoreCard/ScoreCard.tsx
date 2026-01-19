import type { FinalScore } from '../../types';

interface ScoreCardProps {
  score: FinalScore;
  title?: string;
}

type ScoreLevel = 'excellent' | 'good' | 'average' | 'poor' | 'critical';

function getScoreLevel(score: number): ScoreLevel {
  if (score >= 80) return 'excellent';
  if (score >= 60) return 'good';
  if (score >= 40) return 'average';
  if (score >= 20) return 'poor';
  return 'critical';
}

function getScoreColor(score: number): string {
  return `text-score-${getScoreLevel(score)}`;
}

function getScoreBgColor(score: number): string {
  return `bg-score-${getScoreLevel(score)}`;
}

export default function ScoreCard({ score, title = 'Overall Score' }: ScoreCardProps): JSX.Element {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-700 mb-4">{title}</h3>

      <div className="flex items-center justify-center mb-6">
        <div
          className={`w-32 h-32 rounded-full flex items-center justify-center ${getScoreBgColor(score.score)} bg-opacity-20`}
        >
          <span className={`text-4xl font-bold ${getScoreColor(score.score)}`}>
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
        <DimensionBadge label="Risk" score={score.dimensions.p_risk} />
      </div>
    </div>
  );
}

interface DimensionBadgeProps {
  label: string;
  score: number;
}

function DimensionBadge({ label, score }: DimensionBadgeProps): JSX.Element {
  return (
    <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`font-semibold ${getScoreColor(score)}`}>{score}</span>
    </div>
  );
}
