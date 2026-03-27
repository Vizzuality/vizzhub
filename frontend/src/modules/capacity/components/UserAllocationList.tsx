import { useMemo, useState } from 'react';
import { ABSENCE_COLOR, ITEM_PALETTE, OTHER_COLOR } from '@/modules/capacity/utils/constants';
import type { AllocationSegment, UserAllocation } from '@/modules/capacity/types/allocation';
import { AllocationBar, ShowMoreButtons } from '@/modules/capacity/components/AllocationBar';
import type { BarSegment } from '@/modules/capacity/components/AllocationBar';

const PAGE_SIZE = 10;

const OPACITY_BY_TYPE: Record<AllocationSegment['type'], number> = {
  billable: 1,
  absence: 0.5,
  other: 0.3,
};

function buildColorMap(users: UserAllocation[]): Map<string, string> {
  const map = new Map<string, string>();
  map.set('__absence__', ABSENCE_COLOR);
  map.set('__other__', OTHER_COLOR);
  let i = 0;
  for (const user of users) {
    for (const seg of user.segments) {
      if (!map.has(seg.project_id)) {
        map.set(seg.project_id, ITEM_PALETTE[i % ITEM_PALETTE.length]);
        i++;
      }
    }
  }
  return map;
}

function toBarSegments(
  segments: AllocationSegment[],
  colorMap: Map<string, string>,
): BarSegment[] {
  return segments.map((seg) => ({
    key: seg.project_id,
    label: seg.project_name,
    avg_percentage: seg.avg_percentage,
    months_active: seg.months_active,
    color: colorMap.get(seg.project_id) ?? OTHER_COLOR,
    opacity: OPACITY_BY_TYPE[seg.type],
  }));
}

interface UserAllocationListProps {
  readonly users: UserAllocation[];
}

export function UserAllocationList({ users }: UserAllocationListProps): JSX.Element {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const colorMap = useMemo(() => buildColorMap(users), [users]);
  const visibleUsers = users.slice(0, visibleCount);

  return (
    <div className="space-y-3">
      {visibleUsers.map((user) => (
        <div key={user.user_id} className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium">{user.name}</span>
            <span className="text-muted-foreground text-xs">
              avg {user.avg_billable_projects} projects &middot;{' '}
              {user.total_distinct_projects} total
            </span>
          </div>
          <AllocationBar segments={toBarSegments(user.segments, colorMap)} />
        </div>
      ))}

      <ShowMoreButtons
        totalCount={users.length}
        visibleCount={visibleCount}
        onShowMore={() => setVisibleCount((c) => c + PAGE_SIZE)}
        onShowAll={() => setVisibleCount(users.length)}
      />

      {users.length === 0 && (
        <p className="text-muted-foreground text-sm">No allocation data available.</p>
      )}
    </div>
  );
}
