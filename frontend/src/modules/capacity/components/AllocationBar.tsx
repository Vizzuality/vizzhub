import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { formatMonths } from '@/modules/capacity/utils/constants';

export interface BarSegment {
  key: string;
  label: string;
  avg_percentage: number;
  months_active: string[];
  color: string;
  opacity?: number;
}

interface AllocationBarProps {
  readonly segments: BarSegment[];
}

export function AllocationBar({ segments }: AllocationBarProps): JSX.Element {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-5 w-full overflow-hidden rounded bg-muted/30">
        {segments.map((seg) => {
          const widthPct = seg.avg_percentage * 100;
          if (widthPct < 0.5) return null;

          return (
            <Tooltip key={seg.key}>
              <TooltipTrigger asChild>
                <div
                  className="h-full min-w-[2px] cursor-default"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: seg.color,
                    opacity: seg.opacity ?? 1.0,
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">{seg.label}</p>
                <p className="text-xs opacity-70">
                  {Math.round(seg.avg_percentage * 100)}%
                </p>
                <p className="text-xs opacity-70">
                  {formatMonths(seg.months_active)}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}

interface ShowMoreButtonsProps {
  readonly totalCount: number;
  readonly visibleCount: number;
  readonly onShowMore: () => void;
  readonly onShowAll: () => void;
}

export function ShowMoreButtons({
  totalCount,
  visibleCount,
  onShowMore,
  onShowAll,
}: ShowMoreButtonsProps): JSX.Element | null {
  if (visibleCount >= totalCount) return null;

  return (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onShowMore}
        className="text-muted-foreground hover:text-foreground text-sm underline"
      >
        Show more ({totalCount - visibleCount} remaining)
      </button>
      <button
        type="button"
        onClick={onShowAll}
        className="text-muted-foreground hover:text-foreground text-sm underline"
      >
        Show all
      </button>
    </div>
  );
}
