import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface MetricItem {
  label: string;
  value: number | string | null;
  suffix?: string;
}

interface SubIndicatorCardProps {
  title: string;
  indicatorValue: number | null;
  indicatorLabel: string;
  indicatorSuffix?: string;
  metrics: MetricItem[];
  description?: string;
  target?: number | null;
  lowerIsBetter?: boolean;
}

export default function SubIndicatorCard({
  title,
  indicatorValue,
  indicatorLabel,
  indicatorSuffix = '%',
  metrics,
  description,
  target,
  lowerIsBetter = true,
}: SubIndicatorCardProps): JSX.Element {
  const formattedValue = indicatorValue !== null
    ? indicatorValue.toFixed(1)
    : '—';

  const getIndicatorColor = (value: number | null): string => {
    if (value === null) return 'text-muted-foreground';
    if (target === null || target === undefined) {
      return 'text-foreground';
    }
    const isGood = lowerIsBetter ? value <= target : value >= target;
    return isGood
      ? 'text-green-600 dark:text-green-400'
      : 'text-red-600 dark:text-red-400';
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg border">
          <div className="space-y-1">
            <span className="text-sm font-medium text-muted-foreground">
              {indicatorLabel}
            </span>
            {target !== null && target !== undefined && (
              <p className="text-xs text-muted-foreground">
                Target: {lowerIsBetter ? '≤' : '≥'}{target}{indicatorSuffix}
              </p>
            )}
          </div>
          <span className={cn(
            'text-3xl font-bold',
            getIndicatorColor(indicatorValue)
          )}>
            {formattedValue}{indicatorValue !== null && indicatorSuffix}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {metrics.map((metric, index) => (
            <div
              key={index}
              className="flex justify-between items-center p-3 bg-muted rounded-lg"
            >
              <span className="text-sm text-muted-foreground">{metric.label}</span>
              <span className="text-base font-medium">
                {metric.value !== null ? metric.value : '—'}
                {metric.value !== null && metric.suffix}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
