import { cn } from '@/lib/utils';

interface IndicatorDisplayProps {
  value: number | null;
  label: string;
  suffix: string;
  target?: number | null;
  lowerIsBetter: boolean;
}

function getIndicatorColor(
  value: number | null,
  target: number | null | undefined,
  lowerIsBetter: boolean,
): string {
  if (value === null) return 'text-muted-foreground';
  if (target === null || target === undefined) {
    return 'text-foreground';
  }
  const isGood = lowerIsBetter ? value <= target : value >= target;
  return isGood ? 'text-score-green' : 'text-score-red';
}

export default function IndicatorDisplay({
  value,
  label,
  suffix,
  target,
  lowerIsBetter,
}: IndicatorDisplayProps): JSX.Element {
  const formattedValue = value !== null ? value.toFixed(1) : '—';

  return (
    <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <span className={cn('text-3xl font-bold', getIndicatorColor(value, target, lowerIsBetter))}>
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
