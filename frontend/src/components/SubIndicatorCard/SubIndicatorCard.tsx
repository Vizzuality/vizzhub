import { Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
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
  formula?: string;
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
  formula,
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
      ? 'text-score-green'
      : 'text-score-red';
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{title}</CardTitle>
            {description && (
              <p className="text-sm text-muted-foreground">
                {description.includes('DORA') ? (
                  <>
                    <span className="text-chart-3">DORA</span>
                    {description.replace('DORA', '')}
                  </>
                ) : (
                  description
                )}
              </p>
            )}
          </div>
          {formula && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="text-muted-foreground hover:text-foreground transition-colors">
                    <Info className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-mono text-xs">{formula}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">
              {indicatorLabel}
            </span>
            <span className={cn(
              'text-3xl font-bold',
              getIndicatorColor(indicatorValue)
            )}>
              {formattedValue}{indicatorValue !== null && indicatorSuffix}
            </span>
          </div>
          {target !== null && target !== undefined && (
            <div className="flex items-center justify-between pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground">KPI</span>
              <span className="text-sm text-foreground">
                {lowerIsBetter ? '≤' : '≥'}{target}{indicatorSuffix}
              </span>
            </div>
          )}
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
