import { TrendingUp, BarChart3, Maximize2, Minimize2, Info } from 'lucide-react';
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface ChartControlsProps {
  readonly showTrend: boolean;
  readonly chartMode: 'line' | 'bar';
  readonly expanded: boolean;
  readonly hasHistoricalData: boolean;
  readonly formula?: string;
  readonly onToggleLine: () => void;
  readonly onToggleBar: () => void;
  readonly onToggleExpand: () => void;
}

export default function ChartControls({
  showTrend,
  chartMode,
  expanded,
  hasHistoricalData,
  formula,
  onToggleLine,
  onToggleBar,
  onToggleExpand,
}: ChartControlsProps): JSX.Element {
  return (
    <div className="flex items-center gap-1">
      {hasHistoricalData && (
        <>
          <TooltipProvider>
            <UITooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={onToggleLine}
                  className={cn(
                    'p-1 rounded transition-colors',
                    showTrend && chartMode === 'line'
                      ? 'text-primary bg-primary/10'
                      : 'text-muted-foreground hover:text-foreground',
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
                  type="button"
                  onClick={onToggleBar}
                  className={cn(
                    'p-1 rounded transition-colors',
                    showTrend && chartMode === 'bar'
                      ? 'text-primary bg-primary/10'
                      : 'text-muted-foreground hover:text-foreground',
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
                    type="button"
                    onClick={onToggleExpand}
                    className={cn(
                      'p-1 rounded transition-colors',
                      expanded
                        ? 'text-primary bg-primary/10'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {expanded ? (
                      <Minimize2 className="h-4 w-4" />
                    ) : (
                      <Maximize2 className="h-4 w-4" />
                    )}
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
              <button type="button" className="p-1 text-muted-foreground hover:text-foreground transition-colors">
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
  );
}
