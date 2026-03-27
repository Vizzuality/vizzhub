import { useState, useCallback, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import { Pencil, Info, TrendingUp, BarChart3, Maximize2, Minimize2 } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { CHART_COLORS } from '@/utils/chartUtils';
import type { HistoricalDataPoint } from '../../types';

export type { HistoricalDataPoint } from '../../types';

const DEFAULT_CHART_COLOR = 'var(--chart-1)';

type ChartMode = 'line' | 'bar';

interface ChartToggleButtonProps {
  readonly mode: ChartMode;
  readonly currentMode: ChartMode;
  readonly showTrend: boolean;
  readonly onToggle: () => void;
  readonly tooltipText: string;
  readonly icon: ReactNode;
}

function ChartToggleButton({
  mode,
  currentMode,
  showTrend,
  onToggle,
  tooltipText,
  icon,
}: ChartToggleButtonProps): JSX.Element {
  const isActive = showTrend && currentMode === mode;
  const buttonClass = isActive
    ? 'text-primary bg-primary/10'
    : 'text-muted-foreground hover:text-foreground';

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button onClick={onToggle} className={cn('p-1 rounded transition-colors', buttonClass)}>
            {icon}
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface ExpandButtonProps {
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
}

function ExpandButton({ isExpanded, onToggle }: ExpandButtonProps): JSX.Element {
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
            <Icon className="h-4 w-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface DimensionBadgeProps {
  readonly dimension: string;
}

function DimensionBadge({ dimension }: DimensionBadgeProps): JSX.Element {
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

interface MetricChartTooltipProps {
  readonly active?: boolean;
  readonly payload?: Array<{ value?: unknown; payload?: { period: string } }>;
  readonly chartColor: string;
  readonly indicatorSuffix: string;
}

function MetricChartTooltip({ active, payload, chartColor, indicatorSuffix }: MetricChartTooltipProps): JSX.Element | null {
  const point = payload?.[0];
  if (!active || !point?.payload) return null;

  const value = point.value as number;
  return (
    <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
      <div className="font-medium">{point.payload.period}</div>
      <div style={{ color: chartColor }}>
        {value?.toFixed(2)}{indicatorSuffix}
      </div>
    </div>
  );
}

interface EditableMetricCardProps<T> {
  readonly title: string;
  readonly description: string;
  readonly tooltipContent: ReactNode;
  readonly indicatorValue?: number | null;
  readonly target?: number | null;
  readonly data: T | null | undefined;
  readonly onSave: (data: T) => Promise<unknown>;
  readonly isPending: boolean;
  readonly renderEditForm: (form: T, setForm: Dispatch<SetStateAction<T>>) => ReactNode;
  readonly renderDisplay: (data: T | null | undefined, indicatorValue: number | null | undefined, target: number | null | undefined) => ReactNode;
  readonly defaultFormState: T;
  readonly editButtonLabel?: string;
  readonly disabled?: boolean;
  readonly disabledContent?: ReactNode;
  readonly historicalData?: HistoricalDataPoint[];
  readonly indicatorSuffix?: string;
  readonly chartColor?: string;
  readonly lowerIsBetter?: boolean;
  readonly dimension?: string;
}

function createChartModeToggleHandler(
  targetMode: ChartMode,
  showTrend: boolean,
  chartMode: ChartMode,
  setShowTrend: (value: boolean) => void,
  setChartMode: (value: ChartMode) => void,
): () => void {
  return (): void => {
    if (showTrend && chartMode === targetMode) {
      setShowTrend(false);
      return;
    }
    setShowTrend(true);
    setChartMode(targetMode);
  };
}

function renderReferenceAreas(
  lowerIsBetter: boolean,
  target: number,
  domainMin: number,
  domainMax: number,
): JSX.Element {
  if (lowerIsBetter) {
    return (
      <>
        <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.green} fillOpacity={0.1} />
        <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.red} fillOpacity={0.1} />
      </>
    );
  }
  return (
    <>
      <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.green} fillOpacity={0.1} />
      <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.red} fillOpacity={0.1} />
    </>
  );
}

function renderReferenceLine(target: number): JSX.Element {
  return (
    <ReferenceLine
      y={target}
      stroke={CHART_COLORS.green}
      strokeWidth={2}
      strokeDasharray="4 2"
      label={{
        value: 'KPI',
        position: 'right',
        fontSize: 9,
        fill: CHART_COLORS.green,
      }}
    />
  );
}

export default function EditableMetricCard<T>({
  title,
  description,
  tooltipContent,
  indicatorValue,
  target,
  data,
  onSave,
  isPending,
  renderEditForm,
  renderDisplay,
  defaultFormState,
  editButtonLabel,
  disabled = false,
  disabledContent,
  historicalData,
  indicatorSuffix = '',
  chartColor = DEFAULT_CHART_COLOR,
  lowerIsBetter = false,
  dimension,
}: EditableMetricCardProps<T>): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<T>(defaultFormState);
  const [showTrend, setShowTrend] = useState(false);
  const [chartMode, setChartMode] = useState<ChartMode>('line');
  const [expanded, setExpanded] = useState(false);

  const hasHistoricalData = Boolean(historicalData && historicalData.length > 1);
  const displayData = historicalData?.slice(-6);

  const handleStartEdit = (): void => {
    setForm(data ?? defaultFormState);
    setIsEditing(true);
  };

  const handleSave = async (): Promise<void> => {
    await onSave(form);
    setIsEditing(false);
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    setForm(data ?? defaultFormState);
  };

  const hasData = data !== null && data !== undefined;
  const buttonLabel = editButtonLabel ?? (hasData ? 'Edit' : 'Add');

  const handleLineToggle = createChartModeToggleHandler('line', showTrend, chartMode, setShowTrend, setChartMode);
  const handleBarToggle = createChartModeToggleHandler('bar', showTrend, chartMode, setShowTrend, setChartMode);

  const renderTooltipContent = useCallback(
    (props: { active?: boolean; payload?: unknown[] }): JSX.Element | null => (
      <MetricChartTooltip
        active={props.active}
        payload={props.payload as MetricChartTooltipProps['payload']}
        chartColor={chartColor}
        indicatorSuffix={indicatorSuffix}
      />
    ),
    [chartColor, indicatorSuffix],
  );

  const renderChart = (chartData: HistoricalDataPoint[], height: number): JSX.Element => {
    const values = chartData.map(d => d.value).filter((v): v is number => v !== null);
    const dataMin = values.length > 0 ? Math.min(...values) : 0;
    const dataMax = values.length > 0 ? Math.max(...values) : 1;
    const targetVal = target ?? (lowerIsBetter ? dataMax : dataMin);
    const padding = (dataMax - dataMin) * 0.1 || 0.1;
    const yMin = Math.min(dataMin, targetVal) - padding;
    const yMax = Math.max(dataMax, targetVal) + padding;
    const domainMin = Math.max(0, yMin);
    const domainMax = yMax;

    const hasTarget = target !== null && target !== undefined;
    const referenceAreas = hasTarget && renderReferenceAreas(lowerIsBetter, target, domainMin, domainMax);
    const referenceLine = hasTarget && renderReferenceLine(target);

    return (
      <ResponsiveContainer width="100%" height={height}>
        {chartMode === 'line' ? (
          <LineChart data={chartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v.toFixed(1)}`} />
            {referenceLine}
            <RechartsTooltip content={renderTooltipContent} />
            <Line type="monotone" dataKey="value" stroke={chartColor} strokeWidth={2} dot={{ r: 3, fill: chartColor }} connectNulls />
          </LineChart>
        ) : (
          <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }} maxBarSize={60}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v.toFixed(1)}`} />
            {referenceLine}
            <RechartsTooltip cursor={false} content={renderTooltipContent} />
            <Bar dataKey="value" fill={chartColor} radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    );
  };

  const shouldShowInlineChart = showTrend && hasHistoricalData && displayData;

  return (
    <Card className={cn(disabled && 'opacity-60')}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              {dimension && <DimensionBadge dimension={dimension} />}
              {title}
            </CardTitle>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <div className="flex items-center gap-1">
            {hasHistoricalData && (
              <>
                <ChartToggleButton
                  mode="line"
                  currentMode={chartMode}
                  showTrend={showTrend}
                  onToggle={handleLineToggle}
                  tooltipText="Cumulative trend"
                  icon={<TrendingUp className="h-4 w-4" />}
                />
                <ChartToggleButton
                  mode="bar"
                  currentMode={chartMode}
                  showTrend={showTrend}
                  onToggle={handleBarToggle}
                  tooltipText="Monthly data"
                  icon={<BarChart3 className="h-4 w-4" />}
                />
                {showTrend && (
                  <ExpandButton isExpanded={expanded} onToggle={() => setExpanded(!expanded)} />
                )}
              </>
            )}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="p-1 text-muted-foreground hover:text-foreground transition-colors">
                    <Info className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">{tooltipContent}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {disabled && disabledContent ? (
          disabledContent
        ) : (
          <>
            {shouldShowInlineChart && (
              <div className="pb-2">
                {renderChart(displayData, 140)}
              </div>
            )}
            <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
              {isEditing ? (
                <div className="space-y-4">
                  {renderEditForm(form, setForm)}
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" onClick={handleSave} disabled={isPending}>
                      {isPending ? 'Saving...' : 'Save'}
                    </Button>
                    <Button size="sm" variant="outline" onClick={handleCancel}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                renderDisplay(data, indicatorValue, target)
              )}
            </div>
            {!isEditing && (
              <Button variant="outline" size="sm" className="w-full" onClick={handleStartEdit}>
                <Pencil className="w-4 h-4 mr-2" />
                {buttonLabel}
              </Button>
            )}
          </>
        )}
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
