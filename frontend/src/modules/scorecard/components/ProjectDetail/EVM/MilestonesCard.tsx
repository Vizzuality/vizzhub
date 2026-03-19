import { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp, Maximize2, Minimize2 } from 'lucide-react';
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
import type { Milestone, HistoricalDataPoint } from '@/modules/scorecard/types';

const CHART_COLOR = 'var(--chart-1)';

function getMilestoneDotClass(value: number, target: number): string {
  if (value >= target) return 'bg-aux-neon-grass';
  if (value >= target * 0.9) return 'bg-aux-yellow';
  return 'bg-aux-red';
}

interface MilestonesChartTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ value?: number; payload?: HistoricalDataPoint }>;
}

function MilestonesChartTooltip({ active, payload }: MilestonesChartTooltipProps): JSX.Element | null {
  const point = payload?.[0];
  if (!active || !point) return null;
  const v = point.value;
  return (
    <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
      <div className="font-medium">{point.payload?.period}</div>
      <div style={{ color: CHART_COLOR }}>{v?.toFixed(0)}%</div>
    </div>
  );
}

interface MilestonesHistoricalChartProps {
  readonly chartData: HistoricalDataPoint[];
  readonly height: number;
  readonly targetPct: number;
}

function MilestonesHistoricalChart({
  chartData,
  height,
  targetPct,
}: MilestonesHistoricalChartProps): JSX.Element {
  const values = chartData.map(d => d.value).filter((v): v is number => v !== null);
  const dataMin = values.length > 0 ? Math.min(...values) : 0;
  const dataMax = values.length > 0 ? Math.max(...values) : 100;
  const padding = (dataMax - dataMin) * 0.15 || 10;
  const domainMin = Math.max(0, Math.floor(Math.min(dataMin, targetPct) - padding));
  const domainMax = Math.min(100, Math.ceil(Math.max(dataMax, targetPct) + padding));

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
        <RechartsTooltip content={MilestonesChartTooltip} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={CHART_COLOR}
          strokeWidth={2}
          dot={{ r: 2, fill: CHART_COLOR }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface MilestonesCardProps {
  milestones: Milestone[] | null | undefined;
  onTimeMilestones: number | null;
  milestonesTarget: number;
  isExpanded: boolean;
  onToggle: () => void;
  historicalData?: HistoricalDataPoint[];
}

export default function MilestonesCard({
  milestones,
  onTimeMilestones,
  milestonesTarget,
  isExpanded,
  onToggle,
  historicalData,
}: MilestonesCardProps): JSX.Element {
  const [showTrend, setShowTrend] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const milestonesTargetPct = milestonesTarget * 100;
  const hasHistoricalData = historicalData && historicalData.length > 1;
  const displayData = historicalData?.slice(-6);

  const handleTrendClick = (e: React.MouseEvent): void => {
    e.stopPropagation();
    setShowTrend(!showTrend);
  };

  const handleExpandClick = (e: React.MouseEvent): void => {
    e.stopPropagation();
    setExpanded(!expanded);
  };

  return (
    <div className="p-4 bg-muted/50 rounded-lg border text-left">
      <button
        onClick={onToggle}
        className="w-full text-left hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <p className="text-sm text-muted-foreground">On-Time Milestones</p>
            <InfoTooltip>
              <p className="text-sm">On-time delivery rate</p>
              <p className="text-xs text-white/70 mt-1">Target: {milestonesTargetPct.toFixed(0)}%</p>
            </InfoTooltip>
          </div>
          <div className="flex items-center gap-1">
            {hasHistoricalData && (
              <>
                <button
                  onClick={handleTrendClick}
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
                          onClick={handleExpandClick}
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
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        </div>
      </button>

      {showTrend && hasHistoricalData && displayData && (
        <div className="mb-2">
          <MilestonesHistoricalChart
            chartData={displayData}
            height={100}
            targetPct={milestonesTargetPct}
          />
        </div>
      )}

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>On-Time Milestones - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-80">
            {historicalData && (
              <MilestonesHistoricalChart
                chartData={historicalData}
                height={320}
                targetPct={milestonesTargetPct}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>

      {onTimeMilestones !== null ? (
        <>
          <p className="text-xl font-semibold text-foreground flex items-center gap-1.5">
            <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', getMilestoneDotClass(onTimeMilestones, milestonesTarget))} />
            {(onTimeMilestones * 100).toFixed(0)}%
          </p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">
              {milestones?.length || 0} milestone
              {(milestones?.length || 0) !== 1 ? 's' : ''}
            </p>
            <p className="text-xs text-primary">expand to edit</p>
          </div>
        </>
      ) : (
        <>
          <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">No milestones</p>
            <p className="text-xs text-primary">expand to edit</p>
          </div>
        </>
      )}
    </div>
  );
}
