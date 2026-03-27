import { useMemo, useState } from 'react';
import { ITEM_PALETTE } from '@/modules/capacity/utils/constants';
import type { ProjectAllocation, ProjectAllocationSegment } from '@/modules/capacity/types/allocation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';

const PAGE_SIZE = 10;

function buildColorMap(projects: ProjectAllocation[]): Map<string, string> {
  const map = new Map<string, string>();
  let i = 0;
  for (const project of projects) {
    for (const seg of project.segments) {
      if (!map.has(seg.user_id)) {
        map.set(seg.user_id, ITEM_PALETTE[i % ITEM_PALETTE.length]);
        i++;
      }
    }
  }
  return map;
}

function formatMonths(months: string[]): string {
  return months
    .map((m) => {
      const [year, month] = m.split('-');
      const date = new Date(Number(year), Number(month) - 1);
      return date.toLocaleDateString('en', { month: 'short', year: 'numeric' });
    })
    .join(', ');
}

interface SegmentBarProps {
  readonly segments: ProjectAllocationSegment[];
  readonly colorMap: Map<string, string>;
}

function SegmentBar({ segments, colorMap }: SegmentBarProps): JSX.Element {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-5 w-full overflow-hidden rounded bg-muted/30">
        {segments.map((seg) => {
          const widthPct = seg.avg_percentage * 100;
          if (widthPct < 0.5) return null;
          const color = colorMap.get(seg.user_id) ?? '#6b7280';

          return (
            <Tooltip key={seg.user_id}>
              <TooltipTrigger asChild>
                <div
                  className="h-full min-w-[2px] cursor-default"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: color,
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">{seg.user_name}</p>
                <p className="text-muted-foreground text-xs">
                  {Math.round(seg.avg_percentage * 100)}%
                </p>
                <p className="text-muted-foreground text-xs">
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

interface ProjectAllocationListProps {
  readonly projects: ProjectAllocation[];
}

export function ProjectAllocationList({ projects }: ProjectAllocationListProps): JSX.Element {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const colorMap = useMemo(() => buildColorMap(projects), [projects]);
  const visibleProjects = projects.slice(0, visibleCount);
  const hasMore = visibleCount < projects.length;

  return (
    <div className="space-y-3">
      {visibleProjects.map((project) => (
        <div key={project.project_id} className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium">{project.name}</span>
            <span className="text-muted-foreground text-xs">
              avg {project.avg_people} people &middot;{' '}
              {project.total_distinct_people} total
            </span>
          </div>
          <SegmentBar segments={project.segments} colorMap={colorMap} />
        </div>
      ))}

      {hasMore && (
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
            className="text-muted-foreground hover:text-foreground text-sm underline"
          >
            Show more ({projects.length - visibleCount} remaining)
          </button>
          <button
            type="button"
            onClick={() => setVisibleCount(projects.length)}
            className="text-muted-foreground hover:text-foreground text-sm underline"
          >
            Show all
          </button>
        </div>
      )}

      {projects.length === 0 && (
        <p className="text-muted-foreground text-sm">No project data available.</p>
      )}
    </div>
  );
}
