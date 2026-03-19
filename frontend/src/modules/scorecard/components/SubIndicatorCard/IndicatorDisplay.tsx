import { cn } from '@/lib/utils';

interface IndicatorDisplayProps {
  readonly value: number | null;
  readonly label: string;
  readonly suffix: string;
  readonly target?: number | null;
  readonly lowerIsBetter: boolean;
}

function getIndicatorDotClass(
  value: number | null,
  target: number | null | undefined,
  lowerIsBetter: boolean,
): string {
  if (value === null) return 'bg-aux-dust-grey';
  if (target === null || target === undefined) return 'bg-aux-dust-grey';
  const isGood = lowerIsBetter ? value <= target : value >= target;
  return isGood ? 'bg-aux-neon-grass' : 'bg-aux-red';
}

export default function IndicatorDisplay({
  value,
  label,
  suffix,
  target,
  lowerIsBetter,
}: IndicatorDisplayProps): JSX.Element {
  const formattedValue = value === null ? '—' : value.toFixed(1);

  return (
    <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
      <div className="flex items-center justify-between gap-2 min-w-0">
        <span className="text-sm font-medium text-muted-foreground truncate">{label}</span>
        <span className="text-3xl font-bold shrink-0 text-foreground flex items-center gap-2">
          <span className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', getIndicatorDotClass(value, target, lowerIsBetter))} />
          {formattedValue}
          {value !== null && suffix}
        </span>
      </div>
      {target !== null && target !== undefined && (
        <div className="flex items-center justify-between pt-2 border-t border-border/50">
          <span className="text-xs text-muted-foreground">KPI</span>
          <span className="text-sm text-foreground">
            {lowerIsBetter ? '≤' : '≥'}
            {target}
            {suffix}
          </span>
        </div>
      )}
    </div>
  );
}
