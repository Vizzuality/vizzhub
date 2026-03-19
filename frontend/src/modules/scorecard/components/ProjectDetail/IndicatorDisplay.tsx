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

const DOT_SIZE_MAP: Record<ScoreTextSize, string> = {
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
  lg: 'w-2.5 h-2.5',
};

function getScoreColor(
  indicatorValue: number | null,
  targetNormalized: number | null
): string {
  if (indicatorValue === null || targetNormalized === null) {
    return 'text-muted-foreground';
  }
  if (indicatorValue >= targetNormalized) {
    return 'text-aux-neon-grass';
  }
  if (indicatorValue >= targetNormalized * 0.9) {
    return 'text-aux-yellow';
  }
  return 'text-aux-red';
}

function getScoreDotBgClass(
  indicatorValue: number | null,
  targetNormalized: number | null
): string {
  if (indicatorValue === null || targetNormalized === null) {
    return 'bg-aux-dust-grey';
  }
  if (indicatorValue >= targetNormalized) {
    return 'bg-aux-neon-grass';
  }
  if (indicatorValue >= targetNormalized * 0.9) {
    return 'bg-aux-yellow';
  }
  return 'bg-aux-red';
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
          'font-bold text-foreground flex items-center gap-1.5',
          TEXT_SIZE_MAP[textSize],
        )}
      >
        <span className={cn('inline-block rounded-full shrink-0', DOT_SIZE_MAP[textSize], getScoreDotBgClass(indicatorValue, targetNormalized))} />
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
    const unitSuffix = unit ? ` ${unit}` : '';
    return `${prefix}${target}${unitSuffix}`;
  };

  return (
    <div className="flex items-center justify-between pt-2 border-t border-border/50">
      <span className="text-xs text-muted-foreground">KPI</span>
      <span className="text-sm text-foreground">{formatValue()}</span>
    </div>
  );
}

export { getScoreColor };
