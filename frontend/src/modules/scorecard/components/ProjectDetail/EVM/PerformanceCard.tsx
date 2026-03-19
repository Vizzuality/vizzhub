import { useState, useCallback } from 'react';
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
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import InfoTooltip from './InfoTooltip';
import type { EVMData, HistoricalDataPoint } from '@/modules/scorecard/types';

const DEFAULT_CHART_COLOR = 'var(--chart-1)';

function getPerformanceDotClass(value: number, target: number): string {
  if (value >= target) return 'bg-aux-neon-grass';
  if (value >= target * 0.9) return 'bg-aux-yellow';
  return 'bg-aux-red';
}

function getPerformanceStatusText(
  value: number,
  statusText: { above: string; equal: string; below: string },
): string {
  if (value > 1) return statusText.above;
  if (value === 1) return statusText.equal;
  return statusText.below;
}

interface PerformanceChartTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ value?: number; payload?: HistoricalDataPoint }>;
  readonly chartColor: string;
}

function PerformanceChartTooltip({
  active,
  payload,
  chartColor,
}: PerformanceChartTooltipProps): JSX.Element | null {
  const point = payload?.[0];
  if (!active || !point) return null;
  const v = point.value;
  return (
    <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
      <div className="font-medium">{point.payload?.period}</div>
      <div style={{ color: chartColor }}>{v?.toFixed(0)}%</div>
    </div>
  );
}

interface PerformanceHistoricalChartProps {
  readonly chartData: HistoricalDataPoint[];
  readonly height: number;
  readonly target: number;
  readonly chartColor: string;
}

function PerformanceHistoricalChart({
  chartData,
  height,
  target,
  chartColor,
}: PerformanceHistoricalChartProps): JSX.Element {
  const values = chartData.map(d => d.value).filter((v): v is number => v !== null);
  const dataMin = values.length > 0 ? Math.min(...values) : 0;
  const dataMax = values.length > 0 ? Math.max(...values) : 100;
  const targetPct = target * 100;
  const padding = (dataMax - dataMin) * 0.15 || 10;
  const domainMin = Math.max(0, Math.floor(Math.min(dataMin, targetPct) - padding));
  const domainMax = Math.ceil(Math.max(dataMax, targetPct) + padding);

  const renderTooltipContent = useCallback(
    ({ active, payload }: { active?: boolean; payload?: unknown[] }): JSX.Element | null => (
      <PerformanceChartTooltip
        active={active}
        payload={payload as PerformanceChartTooltipProps['payload']}
        chartColor={chartColor}
      />
    ),
    [chartColor],
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
        <ReferenceArea y1={targetPct} y2={domainMax} fill="var(--score-green)" fillOpacity={0.1} />
        <ReferenceArea y1={domainMin} y2={targetPct} fill="var(--score-red)" fillOpacity={0.1} />
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
          stroke="var(--score-green)"
          strokeWidth={2}
          strokeDasharray="4 2"
          label={{ value: 'KPI', position: 'right', fontSize: 8, fill: 'var(--score-green)' }}
        />
        <RechartsTooltip content={renderTooltipContent} />
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
}

interface PerformanceCardProps {
  readonly label: string;
  readonly tooltip: string;
  readonly tooltipDetail: string;
  readonly target: number;
  readonly value: number | null;
  readonly statusText: { readonly above: string; readonly equal: string; readonly below: string };
  readonly historicalData?: HistoricalDataPoint[];
  readonly chartColor?: string;
}

interface TrendToggleButtonProps {
  readonly isActive: boolean;
  readonly onToggle: () => void;
}

function TrendToggleButton({ isActive, onToggle }: TrendToggleButtonProps): JSX.Element {
  const buttonClass = isActive
    ? 'text-primary bg-primary/10'
    : 'text-muted-foreground hover:text-foreground';
  return (
    <button onClick={onToggle} className={cn('p-1 rounded transition-colors', buttonClass)}>
      <TrendingUp className="h-3 w-3" />
    </button>
  );
}

interface ExpandToggleButtonProps {
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
}

function ExpandToggleButton({ isExpanded, onToggle }: ExpandToggleButtonProps): JSX.Element {
  const buttonClass = isExpanded
    ? 'text-primary bg-primary/10'
    : 'text-muted-foreground hover:text-foreground';
  const Icon = isExpanded ? Minimize2 : Maximize2;
  const tooltipText = isExpanded ? 'Collapse' : 'Expand';

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button onClick={onToggle} className={cn('p-1 rounded transition-colors', buttonClass)}>
            <Icon className="h-3 w-3" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface ValueDisplayProps {
  readonly value: number | null;
  readonly target: number;
  readonly statusText: { readonly above: string; readonly equal: string; readonly below: string };
}

function ValueDisplay({ value, target, statusText }: ValueDisplayProps): JSX.Element {
  if (value === null) {
    return <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>;
  }

  return (
    <>
      <p className="text-xl font-semibold text-foreground flex items-center gap-1.5">
        <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', getPerformanceDotClass(value, target))} />
        {(value * 100).toFixed(0)}%
      </p>
      <p className="text-xs text-muted-foreground">
        {getPerformanceStatusText(value, statusText)}
      </p>
    </>
  );
}

export function PerformanceCard({
  label,
  tooltip,
  tooltipDetail,
  target,
  value,
  statusText,
  historicalData,
  chartColor = DEFAULT_CHART_COLOR,
}: PerformanceCardProps): JSX.Element {
  const [showTrend, setShowTrend] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const hasHistoricalData = Boolean(historicalData && historicalData.length > 1);
  const displayData = historicalData?.slice(-6);
  const shouldShowInlineChart = showTrend && hasHistoricalData && displayData;

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
              <TrendToggleButton isActive={showTrend} onToggle={() => setShowTrend(!showTrend)} />
              {showTrend && (
                <ExpandToggleButton isExpanded={expanded} onToggle={() => setExpanded(!expanded)} />
              )}
            </>
          )}
          <span className="text-sm text-foreground">&ge;{(target * 100).toFixed(0)}%</span>
        </div>
      </div>

      {shouldShowInlineChart && (
        <div className="mb-2">
          <PerformanceHistoricalChart
            chartData={displayData}
            height={100}
            target={target}
            chartColor={chartColor}
          />
        </div>
      )}

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{label} - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && (
              <PerformanceHistoricalChart
                chartData={historicalData}
                height={320}
                target={target}
                chartColor={chartColor}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>

      <ValueDisplay value={value} target={target} statusText={statusText} />
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
