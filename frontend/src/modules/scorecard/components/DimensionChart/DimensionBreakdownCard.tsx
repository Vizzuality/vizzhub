import { useCallback } from 'react';
import { TrendingUp, Maximize2, Minimize2 } from 'lucide-react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { CHART_TOOLTIP_STYLE } from '@/utils/chartUtils';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useTrendExpand } from '../../hooks/useTrendExpand';
import type { Dimension } from '../../types';

export const DIMENSION_KEYS = [
  'p_time',
  'p_cost',
  'p_quality',
  'p_value',
  'p_satisfaction',
  'p_flow',
  'p_engineering',
  'p_risk',
] as const;

export type DimensionKey = (typeof DIMENSION_KEYS)[number];

export const DIMENSION_LABELS: Record<DimensionKey, string> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk Mgmt',
};

export const DIMENSION_COLORS: Record<DimensionKey, string> = {
  p_time: '#3b82f6',
  p_cost: '#10b981',
  p_quality: '#f59e0b',
  p_value: '#8b5cf6',
  p_satisfaction: '#ec4899',
  p_flow: '#06b6d4',
  p_engineering: '#f97316',
  p_risk: '#ef4444',
};

export const KEY_TO_DIMENSION: Record<DimensionKey, Dimension> = {
  p_time: 'Time',
  p_cost: 'Cost',
  p_quality: 'Quality',
  p_value: 'Value',
  p_satisfaction: 'Satisfaction',
  p_flow: 'Flow',
  p_engineering: 'Engineering',
  p_risk: 'Risk',
};

export interface RadarDataPoint {
  dimension: string;
  score: number;
  isNeutral: boolean;
  fullMark: number;
}

export interface TrendDataPoint {
  period: string;
  [key: string]: string | number;
}

interface RadarTooltipPayload {
  dimension: string;
  score: number;
  isNeutral: boolean;
}

interface RadarTooltipProps {
  active?: boolean;
  payload?: Array<{ payload?: RadarTooltipPayload }>;
}

function RadarTooltipContent({ active, payload }: Readonly<RadarTooltipProps>): JSX.Element | null {
  const item = payload?.[0]?.payload;
  if (!active || !item) return null;
  return (
    <div className="bg-background shadow-lg rounded-lg p-2 border">
      <p className="font-medium">{item.dimension}</p>
      {item.isNeutral ? (
        <p className="text-muted-foreground">No data</p>
      ) : (
        <p className="text-primary">{item.score}/100</p>
      )}
    </div>
  );
}

function getCssVar(name: string, fallback: string): string {
  if (globalThis.window === undefined) return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

interface DimensionBreakdownCardProps {
  readonly radarData: RadarDataPoint[];
  readonly trendData?: TrendDataPoint[];
  readonly visibleDimensions?: Set<Dimension>;
  readonly onToggleDimension?: (dimension: Dimension) => void;
}

export default function DimensionBreakdownCard({
  radarData,
  trendData,
  visibleDimensions,
  onToggleDimension,
}: DimensionBreakdownCardProps): JSX.Element {
  const { showTrend, expanded, toggleTrend, toggleExpand, setExpanded } = useTrendExpand();

  const chartColor = getCssVar('--chart-1', 'oklch(0.8100 0.1000 252)');

  const isVisible = (key: DimensionKey): boolean => {
    if (!visibleDimensions) return true;
    return visibleDimensions.has(KEY_TO_DIMENSION[key]);
  };

  const visibleKeys = DIMENSION_KEYS.filter(isVisible);
  const hasChartData = (trendData?.length ?? 0) > 1;
  const displayData = trendData?.slice(-6) ?? [];

  const customLegend = useCallback(() => (
    <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 mt-2">
      {DIMENSION_KEYS.map((key) => {
        const visible = isVisible(key);
        const dimension = KEY_TO_DIMENSION[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onToggleDimension?.(dimension)}
            className={cn(
              'flex items-center gap-1.5 text-[10px] transition-opacity',
              onToggleDimension && 'cursor-pointer hover:opacity-80',
              !visible && 'opacity-40',
            )}
          >
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: visible ? DIMENSION_COLORS[key] : '#9ca3af' }}
            />
            <span className={cn(!visible && 'line-through')}>
              {DIMENSION_LABELS[key]}
            </span>
          </button>
        );
      })}
    </div>
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ), [visibleDimensions, onToggleDimension]);

  const renderTrendChart = (data: TrendDataPoint[], height: number): JSX.Element => (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
        <XAxis dataKey="period" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
        <Tooltip contentStyle={{ ...CHART_TOOLTIP_STYLE, fontSize: '11px' }} />
        <Legend content={customLegend} />
        {visibleKeys.map((key) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            name={DIMENSION_LABELS[key]}
            stroke={DIMENSION_COLORS[key]}
            strokeWidth={1.5}
            dot={{ r: 2 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Dimension Breakdown</CardTitle>
        {hasChartData && (
          <div className="flex gap-1">
            <TooltipProvider>
              <UITooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={toggleTrend}
                    className={cn(
                      'p-1.5 rounded-md transition-colors',
                      showTrend
                        ? 'bg-primary/20 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted',
                    )}
                  >
                    <TrendingUp className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Historical trend</p>
                </TooltipContent>
              </UITooltip>
            </TooltipProvider>
            {showTrend && (
              <TooltipProvider>
                <UITooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={toggleExpand}
                      className={cn(
                        'p-1.5 rounded-md transition-colors',
                        expanded
                          ? 'bg-primary/20 text-primary'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted',
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
          </div>
        )}
      </CardHeader>

      <CardContent>
        {showTrend && hasChartData ? (
          <div className="w-full h-[350px]">
            {renderTrendChart(displayData, 350)}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 14 }} tickSize={20} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Radar name="Score" dataKey="score" stroke={chartColor} fill={chartColor} fillOpacity={0.5} />
              <Tooltip content={RadarTooltipContent} />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </CardContent>

      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>Dimension Breakdown - Historical Trend</DialogTitle>
          </DialogHeader>
          <div className="w-full h-[450px]">
            {renderTrendChart(trendData ?? [], 450)}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
