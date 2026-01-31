import { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { cn } from '@/lib/utils';
import InfoTooltip from './InfoTooltip';
import type { Milestone } from '@/types';

export interface HistoricalDataPoint {
  period: string;
  value: number | null;
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
  const milestonesTargetPct = milestonesTarget * 100;
  const hasHistoricalData = historicalData && historicalData.length > 1;
  const chartColor = 'oklch(0.7 0.15 250)';

  const handleTrendClick = (e: React.MouseEvent): void => {
    e.stopPropagation();
    setShowTrend(!showTrend);
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
            )}
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        </div>
      </button>

      {showTrend && hasHistoricalData && (() => {
        const values = historicalData!.map(d => d.value).filter((v): v is number => v !== null);
        const dataMin = values.length > 0 ? Math.min(...values) : 0;
        const dataMax = values.length > 0 ? Math.max(...values) : 100;
        const padding = (dataMax - dataMin) * 0.15 || 10;
        const domainMin = Math.max(0, Math.floor(Math.min(dataMin, milestonesTargetPct) - padding));
        const domainMax = Math.min(100, Math.ceil(Math.max(dataMax, milestonesTargetPct) + padding));

        return (
          <div className="mb-2">
            <ResponsiveContainer width="100%" height={100}>
              <LineChart data={historicalData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                <ReferenceArea y1={milestonesTargetPct} y2={domainMax} fill="#22c55e" fillOpacity={0.1} />
                <ReferenceArea y1={domainMin} y2={milestonesTargetPct} fill="#ef4444" fillOpacity={0.1} />
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
                  y={milestonesTargetPct}
                  stroke="#22c55e"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                  label={{ value: 'KPI', position: 'right', fontSize: 8, fill: '#22c55e' }}
                />
                <Tooltip
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
          </div>
        );
      })()}

      {onTimeMilestones !== null ? (
        <>
          <p
            className={cn(
              'text-xl font-semibold',
              onTimeMilestones >= milestonesTarget
                ? 'text-score-green'
                : onTimeMilestones >= milestonesTarget * 0.9
                ? 'text-score-yellow'
                : 'text-score-red'
            )}
          >
            {(onTimeMilestones * 100).toFixed(0)}%
          </p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">
              {milestones?.length || 0} milestone
              {(milestones?.length || 0) !== 1 ? 's' : ''}
            </p>
            <p className="text-xs text-chart-3">expand to edit</p>
          </div>
        </>
      ) : (
        <>
          <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">No milestones</p>
            <p className="text-xs text-chart-3">expand to edit</p>
          </div>
        </>
      )}
    </div>
  );
}
