import { useState } from 'react';
import { Info, TrendingUp, BarChart3, Maximize2, Minimize2 } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
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
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '../../utils/chartUtils';
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

  const hasHistoricalData = historicalData && historicalData.length > 1;
  const displayData = historicalData?.slice(-6);

  const renderChart = (data: HistoricalDataPoint[], height: number) => {
    const values = data.map(d => d.value).filter((v): v is number => v !== null);
    const dataMin = values.length > 0 ? Math.min(...values) : 0;
    const dataMax = values.length > 0 ? Math.max(...values) : 100;
    const targetVal = target ?? (lowerIsBetter ? dataMax : dataMin);
    const padding = (dataMax - dataMin) * 0.1 || 10;
    const yMin = Math.floor(Math.min(dataMin, targetVal) - padding);
    const yMax = Math.ceil(Math.max(dataMax, targetVal) + padding);
    const domainMin = Math.max(0, yMin);
    const domainMax = yMax;

    const referenceAreas = target !== null && target !== undefined && (
      lowerIsBetter ? (
        <>
          <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.green} fillOpacity={0.1} />
          <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.red} fillOpacity={0.1} />
        </>
      ) : (
        <>
          <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.green} fillOpacity={0.1} />
          <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.red} fillOpacity={0.1} />
        </>
      )
    );

    const referenceLine = target !== null && target !== undefined && (
      <ReferenceLine
        y={target}
        stroke={CHART_COLORS.green}
        strokeWidth={2}
        strokeDasharray="4 2"
        label={{
          value: `KPI ${target}`,
          position: 'right',
          fontSize: 9,
          fill: CHART_COLORS.green,
        }}
      />
    );

    const tooltipContent = (props: { active?: boolean; payload?: Array<{ value?: unknown; payload?: { period: string } }> }) => {
      const { active, payload } = props;
      if (active && payload && payload.length && payload[0].payload) {
        const point = payload[0];
        const value = point.value as number;
        return (
          <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
            <div className="font-medium">{point.payload?.period}</div>
            <div style={{ color: chartColor }}>
              {value?.toFixed(1)}{indicatorSuffix}
            </div>
          </div>
        );
      }
      return null;
    };

    return (
      <ResponsiveContainer width="100%" height={height}>
        {chartMode === 'line' ? (
          <LineChart data={data} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v}`} />
            {referenceLine}
            <Tooltip content={tooltipContent} />
            <Line type="monotone" dataKey="value" stroke={chartColor} strokeWidth={2} dot={{ r: 3, fill: chartColor }} connectNulls />
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v}`} />
            {referenceLine}
            <Tooltip cursor={false} content={tooltipContent} />
            <Bar dataKey="value" fill={chartColor} radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    );
  };

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
          <div className="flex items-center gap-1">
            {hasHistoricalData && (
              <>
                <TooltipProvider>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => {
                          if (showTrend && chartMode === 'line') {
                            setShowTrend(false);
                            setExpanded(false);
                          } else {
                            setShowTrend(true);
                            setChartMode('line');
                          }
                        }}
                        className={cn(
                          'p-1 rounded transition-colors',
                          showTrend && chartMode === 'line'
                            ? 'text-primary bg-primary/10'
                            : 'text-muted-foreground hover:text-foreground'
                        )}
                      >
                        <TrendingUp className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">Cumulative trend</p>
                    </TooltipContent>
                  </UITooltip>
                </TooltipProvider>
                <TooltipProvider>
                  <UITooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => {
                          if (showTrend && chartMode === 'bar') {
                            setShowTrend(false);
                            setExpanded(false);
                          } else {
                            setShowTrend(true);
                            setChartMode('bar');
                          }
                        }}
                        className={cn(
                          'p-1 rounded transition-colors',
                          showTrend && chartMode === 'bar'
                            ? 'text-primary bg-primary/10'
                            : 'text-muted-foreground hover:text-foreground'
                        )}
                      >
                        <BarChart3 className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">Monthly data</p>
                    </TooltipContent>
                  </UITooltip>
                </TooltipProvider>
                {showTrend && (
                  <TooltipProvider>
                    <UITooltip>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() => setExpanded(!expanded)}
                          className={cn(
                            'p-1 rounded transition-colors',
                            expanded
                              ? 'text-primary bg-primary/10'
                              : 'text-muted-foreground hover:text-foreground'
                          )}
                        >
                          {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">{expanded ? 'Collapse' : 'Expand'}</p>
                      </TooltipContent>
                    </UITooltip>
                  </TooltipProvider>
                )}
              </>
            )}
            {formula && (
              <TooltipProvider>
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button className="p-1 text-muted-foreground hover:text-foreground transition-colors">
                      <Info className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="font-mono text-xs">{formula}</p>
                  </TooltipContent>
                </UITooltip>
              </TooltipProvider>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Trend Chart - shown when trend is active */}
        {showTrend && hasHistoricalData && displayData && (
          <div className="pb-2">
            {renderChart(displayData, 140)}
          </div>
        )}

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

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{title} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && renderChart(historicalData, 320)}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
