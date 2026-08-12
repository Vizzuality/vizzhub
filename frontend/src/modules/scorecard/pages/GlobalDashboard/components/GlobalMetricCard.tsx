import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { TrendingUp, Users, Maximize2, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import IndicatorChart from '../../../components/SubIndicatorCard/IndicatorChart';
import { useTrendExpand } from '../../../hooks/useTrendExpand';
import type { IndicatorValue } from '../../../types/global';
import type { MetricKPI, HistoricalDataPoint } from '../types';

interface MetricBadgeProps {
  readonly dimension: string;
}

function MetricBadge({ dimension }: MetricBadgeProps): JSX.Element {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-xs font-semibold text-primary shrink-0 cursor-help">
            {dimension.charAt(0).toUpperCase()}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{dimension} metric</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface GlobalMetricCardProps {
  readonly label: string;
  readonly dimension: string;
  readonly indicator: IndicatorValue;
  readonly format?: 'ratio' | 'percent' | 'number' | 'hours' | 'days';
  readonly invert?: boolean;
  readonly kpis?: MetricKPI[];
  readonly historicalData?: HistoricalDataPoint[];
  readonly target?: number | null;
}

export default function GlobalMetricCard({
  label,
  dimension,
  indicator,
  format = 'ratio',
  invert = false,
  kpis = [],
  historicalData,
  target,
}: GlobalMetricCardProps): JSX.Element {
  const { showTrend, expanded, toggleTrend, toggleExpand, setExpanded } = useTrendExpand();

  const formatValue = (value: number | null): string => {
    if (value === null) return '—';
    switch (format) {
      case 'ratio':
        return `${(value * 100).toFixed(1)}%`;
      case 'percent':
        return `${value.toFixed(1)}%`;
      case 'hours':
        return `${value.toFixed(1)}h`;
      case 'days':
        return `${value.toFixed(1)}d`;
      case 'number':
        return value.toFixed(1);
      default:
        return value.toFixed(2);
    }
  };

  const getColor = (value: number | null): string => {
    if (value === null) return 'text-muted-foreground';
    const threshold = invert ? 0.3 : 0.7;
    const isGood = invert ? value < threshold : value > threshold;
    return isGood ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400';
  };

  const getSuffix = (): string => {
    switch (format) {
      case 'ratio': return '%';
      case 'percent': return '%';
      case 'hours': return 'h';
      case 'days': return 'd';
      default: return '';
    }
  };

  const hasData = indicator.value !== null && indicator.count > 0;
  const hasHistoricalData = historicalData && historicalData.length > 1;
  const displayData = historicalData?.slice(-6);

  return (
    <>
      <Card className={cn(!hasData && 'opacity-60')}>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <MetricBadge dimension={dimension} />
              {label}
            </CardTitle>
            {hasHistoricalData && (
              <div className="flex gap-1">
                {showTrend && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={toggleExpand}
                          className={cn(
                            'p-1 rounded transition-colors',
                            expanded
                              ? 'text-primary bg-primary/10'
                              : 'text-muted-foreground hover:text-foreground',
                          )}
                        >
                          {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">{expanded ? 'Collapse' : 'Expand'}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        onClick={toggleTrend}
                        className={cn(
                          'p-1 rounded transition-colors',
                          showTrend
                            ? 'text-primary bg-primary/10'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        <TrendingUp className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">Historical trend</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {showTrend && hasHistoricalData && displayData ? (
            <div className="h-24 w-full mb-2">
              <IndicatorChart
                data={displayData}
                height={96}
                chartMode="line"
                chartColor="var(--chart-1)"
                target={target}
                lowerIsBetter={invert}
                indicatorSuffix={getSuffix()}
              />
            </div>
          ) : (
            <div className="flex items-start justify-between">
              <div>
                <div className={cn('text-2xl font-bold', getColor(indicator.value))}>
                  {formatValue(indicator.value)}
                </div>
                <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                  <Users className="h-3 w-3" />
                  {indicator.count} project{indicator.count !== 1 ? 's' : ''}
                </p>
              </div>
              {kpis.length > 0 && (
                <div className="text-right space-y-1">
                  {kpis.map((kpi) => (
                    <div key={kpi.label} className="text-xs">
                      <span className="text-muted-foreground">{kpi.label}: </span>
                      <span className="font-medium">{kpi.value ?? '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{label} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && (
              <IndicatorChart
                data={historicalData}
                height={320}
                chartMode="line"
                chartColor="var(--chart-1)"
                target={target}
                lowerIsBetter={invert}
                indicatorSuffix={getSuffix()}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
