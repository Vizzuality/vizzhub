import { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import IndicatorChart from './IndicatorChart';
import ChartControls from './ChartControls';
import IndicatorDisplay from './IndicatorDisplay';
import type { HistoricalDataPoint } from '../../types';

export type { HistoricalDataPoint };

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
  historicalData?: HistoricalDataPoint[];
  chartColor?: string;
  badge?: React.ReactNode;
  dimension?: string;
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
  historicalData,
  chartColor = 'oklch(0.7 0.15 250)',
  badge,
  dimension,
}: SubIndicatorCardProps): JSX.Element {
  const [showTrend, setShowTrend] = useState(false);
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line');
  const [expanded, setExpanded] = useState(false);

  const hasHistoricalData = historicalData && historicalData.length > 1;
  const displayData = historicalData?.slice(-6);

  const handleToggleLine = useCallback(() => {
    if (showTrend && chartMode === 'line') {
      setShowTrend(false);
      setExpanded(false);
    } else {
      setShowTrend(true);
      setChartMode('line');
    }
  }, [showTrend, chartMode]);

  const handleToggleBar = useCallback(() => {
    if (showTrend && chartMode === 'bar') {
      setShowTrend(false);
      setExpanded(false);
    } else {
      setShowTrend(true);
      setChartMode('bar');
    }
  }, [showTrend, chartMode]);

  const handleToggleExpand = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              {dimension && (
                <TooltipProvider>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-xs font-semibold text-chart-3 shrink-0 cursor-help">
                        {dimension.charAt(0).toUpperCase()}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">{dimension} metric</p>
                    </TooltipContent>
                  </UITooltip>
                </TooltipProvider>
              )}
              {title}
              {badge}
            </CardTitle>
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
          <ChartControls
            showTrend={showTrend}
            chartMode={chartMode}
            expanded={expanded}
            hasHistoricalData={Boolean(hasHistoricalData)}
            formula={formula}
            onToggleLine={handleToggleLine}
            onToggleBar={handleToggleBar}
            onToggleExpand={handleToggleExpand}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {showTrend && hasHistoricalData && displayData && (
          <div className="pb-2">
            <IndicatorChart
              data={displayData}
              height={140}
              chartMode={chartMode}
              chartColor={chartColor}
              target={target}
              lowerIsBetter={lowerIsBetter}
              indicatorSuffix={indicatorSuffix}
            />
          </div>
        )}

        <IndicatorDisplay
          value={indicatorValue}
          label={indicatorLabel}
          suffix={indicatorSuffix}
          target={target}
          lowerIsBetter={lowerIsBetter}
        />

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

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{title} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && (
              <IndicatorChart
                data={historicalData}
                height={320}
                chartMode={chartMode}
                chartColor={chartColor}
                target={target}
                lowerIsBetter={lowerIsBetter}
                indicatorSuffix={indicatorSuffix}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
