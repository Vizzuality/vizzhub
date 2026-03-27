import { useMemo, useState } from 'react';
import { ITEM_PALETTE, OTHER_COLOR } from '@/modules/capacity/utils/constants';
import type { ProjectAllocation, ProjectAllocationSegment } from '@/modules/capacity/types/allocation';
import { AllocationBar, ShowMoreButtons } from '@/modules/capacity/components/AllocationBar';
import type { BarSegment } from '@/modules/capacity/components/AllocationBar';

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

function toBarSegments(
  segments: ProjectAllocationSegment[],
  colorMap: Map<string, string>,
): BarSegment[] {
  return segments.map((seg) => ({
    key: seg.user_id,
    label: seg.user_name,
    avg_percentage: seg.avg_percentage,
    months_active: seg.months_active,
    color: colorMap.get(seg.user_id) ?? OTHER_COLOR,
  }));
}

interface ProjectAllocationListProps {
  readonly projects: ProjectAllocation[];
}

export function ProjectAllocationList({ projects }: ProjectAllocationListProps): JSX.Element {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const colorMap = useMemo(() => buildColorMap(projects), [projects]);
  const visibleProjects = projects.slice(0, visibleCount);

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
          <AllocationBar segments={toBarSegments(project.segments, colorMap)} />
        </div>
      ))}

      <ShowMoreButtons
        totalCount={projects.length}
        visibleCount={visibleCount}
        onShowMore={() => setVisibleCount((c) => c + PAGE_SIZE)}
        onShowAll={() => setVisibleCount(projects.length)}
      />

      {projects.length === 0 && (
        <p className="text-muted-foreground text-sm">No project data available.</p>
      )}
    </div>
  );
}
