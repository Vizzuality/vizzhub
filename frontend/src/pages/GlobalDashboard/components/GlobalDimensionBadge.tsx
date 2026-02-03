import { cn } from '@/lib/utils';
import { getScoreColor } from '@/utils/scoreColors';
import type { Dimension } from '../../../types';
import type { ScoreValue } from '../../../types/global';

interface GlobalDimensionBadgeProps {
  readonly label: string;
  readonly dimension: Dimension;
  readonly score: ScoreValue;
  readonly thresholds: { green: number; yellow: number };
  readonly isVisible: boolean;
  readonly onToggle?: (dimension: Dimension) => void;
}

export default function GlobalDimensionBadge({
  label,
  dimension,
  score,
  thresholds,
  isVisible,
  onToggle,
}: GlobalDimensionBadgeProps): JSX.Element {
  const hasData = score.value !== null && score.count > 0;
  const displayValue = hasData ? Math.round(score.value!) : null;
  const isClickable = !!onToggle;

  const content = (
    <>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'w-2.5 h-2.5 rounded-full border-2 transition-colors',
            isVisible
              ? 'bg-chart-3 border-chart-3'
              : 'bg-transparent border-muted-foreground/50',
          )}
        />
        <span
          className={cn(
            'text-base transition-colors',
            isVisible ? 'text-chart-3' : 'text-muted-foreground',
          )}
        >
          {label}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'text-lg font-medium transition-opacity',
            isVisible
              ? getScoreColor(displayValue, thresholds)
              : 'text-muted-foreground',
          )}
        >
          {displayValue ?? '—'}
        </span>
        <span className="text-xs text-muted-foreground">({score.count})</span>
      </div>
    </>
  );

  const baseClassName = cn(
    'flex items-center justify-between p-3 rounded-lg transition-all w-full',
    isVisible ? 'bg-muted' : 'bg-muted/30 opacity-50',
  );

  if (isClickable) {
    return (
      <button type="button" onClick={() => onToggle(dimension)} className={baseClassName}>
        {content}
      </button>
    );
  }

  return <div className={baseClassName}>{content}</div>;
}
