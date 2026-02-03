import { useMemo, useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { MetricsWithScores } from '../../types';
import { formatPeriod, generateMonthRange, type Period } from '../../utils/dateUtils';

interface TimelineSliderProps {
  readonly projectStartDate: string;
  readonly projectFinishedAt?: string | null;
  readonly snapshots: MetricsWithScores[] | undefined;
  readonly selectedPeriod: Period | null;
  readonly onPeriodChange: (period: Period | null) => void;
  readonly isCapturing?: boolean;
}

function getLabelInterval(periodsCount: number): number {
  if (periodsCount > 24) return 6;
  if (periodsCount > 12) return 3;
  return 1;
}

export default function TimelineSlider({
  projectStartDate,
  projectFinishedAt,
  snapshots,
  selectedPeriod,
  onPeriodChange,
  isCapturing = false,
}: TimelineSliderProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);

  const periods = useMemo(
    () => generateMonthRange(projectStartDate, projectFinishedAt),
    [projectStartDate, projectFinishedAt],
  );

  const snapshotSet = useMemo(() => {
    const set = new Set<string>();
    snapshots?.forEach((s) => {
      set.add(`${s.period_year}-${s.period_month}`);
    });
    return set;
  }, [snapshots]);

  const hasData = useCallback(
    (year: number, month: number): boolean => snapshotSet.has(`${year}-${month}`),
    [snapshotSet],
  );

  const isSelected = useCallback(
    (year: number, month: number): boolean =>
      selectedPeriod?.year === year && selectedPeriod?.month === month,
    [selectedPeriod],
  );

  const latestWithData = useMemo((): Period => {
    for (let i = periods.length - 1; i >= 0; i--) {
      const p = periods[i];
      if (hasData(p.year, p.month)) {
        return p;
      }
    }
    return periods[periods.length - 1];
  }, [periods, hasData]);

  const effectivePeriod = selectedPeriod ?? latestWithData;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      const currentIndex = periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      );

      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex - 1]);
      } else if (e.key === 'ArrowRight' && currentIndex < periods.length - 1) {
        e.preventDefault();
        onPeriodChange(periods[currentIndex + 1]);
      }
    },
    [periods, effectivePeriod, onPeriodChange],
  );

  useEffect(() => {
    if (containerRef.current && effectivePeriod) {
      const index = periods.findIndex(
        (p) => p.year === effectivePeriod.year && p.month === effectivePeriod.month,
      );
      const marker = containerRef.current.children[index] as HTMLElement;
      if (marker) {
        marker.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }
    }
  }, [effectivePeriod, periods]);

  const labelInterval = getLabelInterval(periods.length);

  return (
    <div
      className="w-full py-4"
      role="listbox"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      aria-label="Timeline period selector - use arrow keys to navigate"
      aria-activedescendant={`period-${effectivePeriod.year}-${effectivePeriod.month}`}
    >
      <div className="relative">
        {/* Base line */}
        <div className="absolute top-3 left-0 right-0 h-0.5 bg-muted" />

        {/* Markers container */}
        <div
          ref={containerRef}
          className="relative flex justify-between overflow-x-auto pb-6 scrollbar-thin"
          style={{ minWidth: `${periods.length * 40}px` }}
        >
          <TooltipProvider>
            {periods.map((period, index) => {
              const hasPeriodData = hasData(period.year, period.month);
              const isPeriodSelected = isSelected(period.year, period.month);
              const isEffective =
                !selectedPeriod &&
                period.year === latestWithData.year &&
                period.month === latestWithData.month;
              const showLabel = index % labelInterval === 0;

              return (
                <Tooltip key={`${period.year}-${period.month}`}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => onPeriodChange(period)}
                      className={cn(
                        'relative flex flex-col items-center transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        'min-w-[40px]',
                      )}
                    >
                      {/* Marker */}
                      <div
                        className={cn(
                          'w-3 h-3 rounded-full border-2 transition-all',
                          hasPeriodData
                            ? 'bg-primary border-primary'
                            : 'bg-background border-muted-foreground/50',
                          (isPeriodSelected || isEffective) && [
                            'w-5 h-5 ring-4 ring-primary/20',
                            hasPeriodData ? 'bg-primary' : 'border-primary',
                          ],
                          isCapturing &&
                            isPeriodSelected &&
                            'animate-pulse',
                        )}
                      />

                      {/* Label */}
                      {showLabel && (
                        <span
                          className={cn(
                            'absolute top-6 text-xs text-muted-foreground whitespace-nowrap',
                            (isPeriodSelected || isEffective) &&
                              'text-foreground font-medium',
                          )}
                        >
                          {formatPeriod(period.year, period.month)}
                        </span>
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      {formatPeriod(period.year, period.month)}
                      {hasPeriodData ? '' : ' (no data)'}
                    </p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>
      </div>

      {/* Reset button */}
      {selectedPeriod && (
        <button
          type="button"
          onClick={() => onPeriodChange(null)}
          className="mt-2 text-xs text-muted-foreground hover:text-foreground underline"
        >
          Reset to latest
        </button>
      )}
    </div>
  );
}
