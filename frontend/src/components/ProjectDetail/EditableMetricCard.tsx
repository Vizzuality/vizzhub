import { useState, type ReactNode, type Dispatch, type SetStateAction } from 'react';
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
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export interface HistoricalDataPoint {
  period: string;
  value: number | null;
}

interface EditableMetricCardProps<T> {
  title: string;
  description: string;
  tooltipContent: ReactNode;
  indicatorValue?: number | null;
  target?: number | null;
  data: T | null | undefined;
  onSave: (data: T) => Promise<unknown>;
  isPending: boolean;
  renderEditForm: (form: T, setForm: Dispatch<SetStateAction<T>>) => ReactNode;
  renderDisplay: (data: T | null | undefined, indicatorValue: number | null | undefined, target: number | null | undefined) => ReactNode;
  defaultFormState: T;
  editButtonLabel?: string;
  disabled?: boolean;
  disabledContent?: ReactNode;
  historicalData?: HistoricalDataPoint[];
  indicatorSuffix?: string;
  chartColor?: string;
  lowerIsBetter?: boolean;
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
  chartColor = 'oklch(0.7 0.15 250)',
  lowerIsBetter = false,
}: EditableMetricCardProps<T>): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<T>(defaultFormState);
  const [showTrend, setShowTrend] = useState(false);
  const [chartMode, setChartMode] = useState<'line' | 'bar'>('line');
  const [expanded, setExpanded] = useState(false);

  const hasHistoricalData = historicalData && historicalData.length > 1;
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

  const renderChart = (chartData: HistoricalDataPoint[], height: number) => {
    const values = chartData.map(d => d.value).filter((v): v is number => v !== null);
    const dataMin = values.length > 0 ? Math.min(...values) : 0;
    const dataMax = values.length > 0 ? Math.max(...values) : 1;
    const targetVal = target ?? (lowerIsBetter ? dataMax : dataMin);
    const padding = (dataMax - dataMin) * 0.1 || 0.1;
    const yMin = Math.min(dataMin, targetVal) - padding;
    const yMax = Math.max(dataMax, targetVal) + padding;
    const domainMin = Math.max(0, yMin);
    const domainMax = yMax;

    const referenceAreas = target !== null && target !== undefined && (
      lowerIsBetter ? (
        <>
          <ReferenceArea y1={domainMin} y2={target} fill="#22c55e" fillOpacity={0.1} />
          <ReferenceArea y1={target} y2={domainMax} fill="#ef4444" fillOpacity={0.1} />
        </>
      ) : (
        <>
          <ReferenceArea y1={target} y2={domainMax} fill="#22c55e" fillOpacity={0.1} />
          <ReferenceArea y1={domainMin} y2={target} fill="#ef4444" fillOpacity={0.1} />
        </>
      )
    );

    const referenceLine = target !== null && target !== undefined && (
      <ReferenceLine
        y={target}
        stroke="#22c55e"
        strokeWidth={2}
        strokeDasharray="4 2"
        label={{
          value: `KPI`,
          position: 'right',
          fontSize: 9,
          fill: '#22c55e',
        }}
      />
    );

    const tooltipContent = ({ active, payload }: { active?: boolean; payload?: Array<{ value: unknown; payload: { period: string } }> }) => {
      if (active && payload && payload.length) {
        const point = payload[0];
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
      return null;
    };

    return (
      <ResponsiveContainer width="100%" height={height}>
        {chartMode === 'line' ? (
          <LineChart data={chartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v.toFixed(1)}`} />
            {referenceLine}
            <RechartsTooltip content={tooltipContent} />
            <Line type="monotone" dataKey="value" stroke={chartColor} strokeWidth={2} dot={{ r: 3, fill: chartColor }} connectNulls />
          </LineChart>
        ) : (
          <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
            {referenceAreas}
            <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
            <YAxis domain={[domainMin, domainMax]} tick={{ fontSize: 9 }} tickLine={false} axisLine={false} width={35} tickFormatter={(v) => `${v.toFixed(1)}`} />
            {referenceLine}
            <RechartsTooltip cursor={false} content={tooltipContent} />
            <Bar dataKey="value" fill={chartColor} radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    );
  };

  return (
    <Card className={cn(disabled && 'opacity-60')}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{title}</CardTitle>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <div className="flex items-center gap-1">
            {hasHistoricalData && (
              <>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => {
                          if (showTrend && chartMode === 'line') {
                            setShowTrend(false);
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
                  </Tooltip>
                </TooltipProvider>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => {
                          if (showTrend && chartMode === 'bar') {
                            setShowTrend(false);
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
                  </Tooltip>
                </TooltipProvider>
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
                          {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
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
            {showTrend && hasHistoricalData && displayData && (
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
