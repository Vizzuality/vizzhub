import type { FinalScore } from '../../types';

interface ScoreCardProps {
  score: FinalScore;
  title?: string;
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-score-excellent';
  if (score >= 60) return 'text-score-good';
  if (score >= 40) return 'text-score-average';
  if (score >= 20) return 'text-score-poor';
  return 'text-score-critical';
}

function getScoreBgColor(score: number): string {
  if (score >= 80) return 'bg-score-excellent';
  if (score >= 60) return 'bg-score-good';
  if (score >= 40) return 'bg-score-average';
  if (score >= 20) return 'bg-score-poor';
  return 'bg-score-critical';
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
