import { cn } from '@/lib/utils';

type ScoreTextSize = 'sm' | 'md' | 'lg';

interface IndicatorScoreDisplayProps {
  label: string;
  indicatorValue: number | null;
  target: number | null;
  textSize?: ScoreTextSize;
}

const TEXT_SIZE_MAP: Record<ScoreTextSize, string> = {
  sm: 'text-xl',
  md: 'text-2xl',
  lg: 'text-3xl',
};

function getScoreColor(
  indicatorValue: number | null,
  targetNormalized: number | null
): string {
  if (indicatorValue === null || targetNormalized === null) {
    return 'text-muted-foreground';
  }
  if (indicatorValue >= targetNormalized) {
    return 'text-score-green';
  }
  if (indicatorValue >= targetNormalized * 0.9) {
    return 'text-score-yellow';
  }
  return 'text-score-red';
}

export function IndicatorScoreDisplay({
  label,
  indicatorValue,
  target,
  textSize = 'lg',
}: IndicatorScoreDisplayProps): JSX.Element {
  const targetNormalized = target === null ? null : target / 100;

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      <span
        className={cn(
          'font-bold',
          TEXT_SIZE_MAP[textSize],
          getScoreColor(indicatorValue, targetNormalized)
        )}
      >
        {indicatorValue === null
          ? '—'
          : `${Math.round(indicatorValue * 100)}%`}
      </span>
    </div>
  );
}

interface KPIDisplayProps {
  target: number | null;
  format?: 'percentage' | 'count';
  comparison?: 'gte' | 'lte';
  unit?: string;
}

export function KPIDisplay({
  target,
  format = 'percentage',
  comparison = 'gte',
  unit,
}: KPIDisplayProps): JSX.Element {
  const formatValue = (): string => {
    if (target === null) return '—';
    const prefix = comparison === 'gte' ? '≥' : '≤';
    if (format === 'percentage') {
      return `${prefix}${target}%`;
    }
    return `${prefix}${target}${unit ? ` ${unit}` : ''}`;
  };

  return (
    <div className="flex items-center justify-between pt-2 border-t border-border/50">
      <span className="text-xs text-muted-foreground">KPI</span>
      <span className="text-sm text-foreground">{formatValue()}</span>
    </div>
  );
}

export { getScoreColor };
