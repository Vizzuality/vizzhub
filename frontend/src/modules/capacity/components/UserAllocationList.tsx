import { useMemo, useState } from 'react';
import { ABSENCE_COLOR, ITEM_PALETTE } from '@/modules/capacity/utils/constants';
import type { AllocationSegment, UserAllocation } from '@/modules/capacity/types/allocation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';

const PAGE_SIZE = 10;

const OTHER_COLOR = '#6b7280';

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

function formatMonths(months: string[]): string {
  return months
    .map((m) => {
      const [year, month] = m.split('-');
      const date = new Date(Number(year), Number(month) - 1);
      return date.toLocaleDateString('en', { month: 'short', year: 'numeric' });
    })
    .join(', ');
}

function opacityForType(type: AllocationSegment['type']): number {
  if (type === 'billable') return 1.0;
  if (type === 'absence') return 0.5;
  return 0.3;
}

interface SegmentBarProps {
  readonly segments: AllocationSegment[];
  readonly colorMap: Map<string, string>;
}

function SegmentBar({ segments, colorMap }: SegmentBarProps): JSX.Element {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-5 w-full overflow-hidden rounded bg-muted/30">
        {segments.map((seg) => {
          const widthPct = seg.avg_percentage * 100;
          if (widthPct < 0.5) return null;
          const color = colorMap.get(seg.project_id) ?? '#6b7280';

          return (
            <Tooltip key={seg.project_id}>
              <TooltipTrigger asChild>
                <div
                  className="h-full min-w-[2px] cursor-default"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    opacity: opacityForType(seg.type),
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">{seg.project_name}</p>
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

interface UserAllocationListProps {
  readonly users: UserAllocation[];
}

export function UserAllocationList({ users }: UserAllocationListProps): JSX.Element {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const colorMap = useMemo(() => buildColorMap(users), [users]);
  const visibleUsers = users.slice(0, visibleCount);
  const hasMore = visibleCount < users.length;

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
          <SegmentBar segments={user.segments} colorMap={colorMap} />
        </div>
      ))}

      {hasMore && (
        <button
          type="button"
          onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
          className="text-muted-foreground hover:text-foreground text-sm underline"
        >
          Show more ({users.length - visibleCount} remaining)
        </button>
      )}

      {users.length === 0 && (
        <p className="text-muted-foreground text-sm">No allocation data available.</p>
      )}
    </div>
  );
}
