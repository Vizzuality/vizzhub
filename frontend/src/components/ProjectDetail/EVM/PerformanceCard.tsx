import { useState } from 'react';
import { TrendingUp, Maximize2, Minimize2 } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { cn } from '@/lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import InfoTooltip from './InfoTooltip';
import type { EVMData } from '@/types';

export interface HistoricalDataPoint {
  period: string;
  value: number | null;
}

interface PerformanceCardProps {
  label: string;
  tooltip: string;
  tooltipDetail: string;
  target: number;
  value: number | null;
  statusText: { above: string; equal: string; below: string };
  historicalData?: HistoricalDataPoint[];
  chartColor?: string;
}

export function PerformanceCard({
  label,
  tooltip,
  tooltipDetail,
  target,
  value,
  statusText,
  historicalData,
  chartColor = 'oklch(0.7 0.15 250)',
}: PerformanceCardProps): JSX.Element {
  const [showTrend, setShowTrend] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const hasHistoricalData = historicalData && historicalData.length > 1;
  const displayData = historicalData?.slice(-6);

  const renderChart = (chartData: HistoricalDataPoint[], height: number) => {
    const values = chartData.map(d => d.value).filter((v): v is number => v !== null);
    const dataMin = values.length > 0 ? Math.min(...values) : 0;
    const dataMax = values.length > 0 ? Math.max(...values) : 100;
    const targetPct = target * 100;
    const padding = (dataMax - dataMin) * 0.15 || 10;
    const domainMin = Math.max(0, Math.floor(Math.min(dataMin, targetPct) - padding));
    const domainMax = Math.ceil(Math.max(dataMax, targetPct) + padding);

    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <ReferenceArea y1={targetPct} y2={domainMax} fill="#22c55e" fillOpacity={0.1} />
          <ReferenceArea y1={domainMin} y2={targetPct} fill="#ef4444" fillOpacity={0.1} />
          <XAxis dataKey="period" tick={{ fontSize: 8 }} tickLine={false} axisLine={false} />
          <YAxis
            domain={[domainMin, domainMax]}
            tick={{ fontSize: 8 }}
            tickLine={false}
            axisLine={false}
            width={30}
            tickFormatter={(v) => `${v}%`}
          />
          <ReferenceLine
            y={targetPct}
            stroke="#22c55e"
            strokeWidth={2}
            strokeDasharray="4 2"
            label={{ value: 'KPI', position: 'right', fontSize: 8, fill: '#22c55e' }}
          />
          <RechartsTooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const point = payload[0];
                const v = point.value as number;
                return (
                  <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
                    <div className="font-medium">{point.payload.period}</div>
                    <div style={{ color: chartColor }}>{v?.toFixed(0)}%</div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={chartColor}
            strokeWidth={2}
            dot={{ r: 2, fill: chartColor }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">{label}</p>
          <InfoTooltip>
            <p className="text-sm">{tooltip}</p>
            <p className="text-xs text-white/70 mt-1">{tooltipDetail}</p>
          </InfoTooltip>
        </div>
        <div className="flex items-center gap-1">
          {hasHistoricalData && (
            <>
              <button
                onClick={() => setShowTrend(!showTrend)}
                className={cn(
                  'p-1 rounded transition-colors',
                  showTrend
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <TrendingUp className="h-3 w-3" />
              </button>
              {showTrend && (
                <TooltipProvider>
                  <Tooltip>
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
                        {expanded ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-xs">{expanded ? 'Collapse' : 'Expand'}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </>
          )}
          <span className="text-sm text-foreground">&ge;{(target * 100).toFixed(0)}%</span>
        </div>
      </div>

      {showTrend && hasHistoricalData && displayData && (
        <div className="mb-2">
          {renderChart(displayData, 100)}
        </div>
      )}

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{label} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && renderChart(historicalData, 320)}
          </div>
        </DialogContent>
      </Dialog>

      {value !== null ? (
        <>
          <p
            className={cn(
              'text-xl font-semibold',
              value >= target
                ? 'text-score-green'
                : value >= target * 0.9
                ? 'text-score-yellow'
                : 'text-score-red'
            )}
          >
            {(value * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-muted-foreground">
            {value > 1 ? statusText.above : value === 1 ? statusText.equal : statusText.below}
          </p>
        </>
      ) : (
        <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>
      )}
    </div>
  );
}

interface SPICardProps {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
  historicalData?: HistoricalDataPoint[];
}

export function SPICard({ evmData, getTarget, historicalData }: SPICardProps): JSX.Element {
  const target = getTarget('target_spi') ?? 0.8;
  const value = evmData.percent_planned > 0
    ? evmData.percent_completed / evmData.percent_planned
    : null;

  return (
    <PerformanceCard
      label="Schedule Performance (SPI)"
      tooltip="Work Completed / Expected Progress"
      tooltipDetail=">1 = ahead, 1 = on track, <1 = behind"
      target={target}
      value={value}
      statusText={{ above: 'Ahead of schedule', equal: 'On schedule', below: 'Behind schedule' }}
      historicalData={historicalData}
    />
  );
}

interface CPICardProps {
  evmData: EVMData;
  getTarget: (name: string) => number | null;
  historicalData?: HistoricalDataPoint[];
}

export function CPICard({ evmData, getTarget, historicalData }: CPICardProps): JSX.Element {
  const target = getTarget('target_cpi') ?? 0.8;
  const value = evmData.cost_to_date > 0
    ? (evmData.budget_total * evmData.percent_completed) / evmData.cost_to_date
    : null;

  return (
    <PerformanceCard
      label="Cost Performance (CPI)"
      tooltip="Earned Value / Actual Cost"
      tooltipDetail=">1 = under budget, 1 = on budget, <1 = over budget"
      target={target}
      value={value}
      statusText={{ above: 'Under budget', equal: 'On budget', below: 'Over budget' }}
      historicalData={historicalData}
    />
  );
}
