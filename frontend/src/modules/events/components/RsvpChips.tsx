import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { useSetRsvp, useDeleteRsvp } from '../hooks/useRsvp';
import { RSVP_COLORS, RSVP_LABELS, RSVP_ICONS } from '../utils/constants';
import type { RsvpStatus, UserSummary } from '../types/events';

const STATUSES: RsvpStatus[] = ['going', 'maybe', 'not_going'];

interface RsvpChipsProps {
  readonly eventId: string;
  readonly counts: Record<RsvpStatus, number>;
  readonly myStatus: RsvpStatus | null;
  readonly names?: Record<RsvpStatus, UserSummary[]>;
  readonly onHover?: (status: RsvpStatus) => void;
  readonly size?: 'sm' | 'md';
}

export function RsvpChips({
  eventId,
  counts,
  myStatus,
  names,
  onHover,
  size = 'md',
}: RsvpChipsProps): JSX.Element {
  const setRsvp = useSetRsvp();
  const deleteRsvp = useDeleteRsvp();

  const handleClick = (status: RsvpStatus): void => {
    if (status === myStatus) {
      deleteRsvp.mutate({ eventId });
    } else {
      setRsvp.mutate({ eventId, status });
    }
  };

  const base =
    size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-0.5';

  return (
    <TooltipProvider>
      <div className="flex items-center gap-1">
        {STATUSES.map((status) => {
          const count = counts[status] ?? 0;
          const isMine = myStatus === status;
          const list = names?.[status] ?? [];
          return (
            <Tooltip key={status}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClick(status);
                  }}
                  onMouseEnter={() => onHover?.(status)}
                  aria-label={`${RSVP_LABELS[status]} (${count})`}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border font-medium',
                    base,
                    RSVP_COLORS[status],
                    isMine && 'ring-2 ring-offset-1 ring-current',
                  )}
                >
                  <span aria-hidden>{RSVP_ICONS[status]}</span>
                  <span>{count}</span>
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <div className="text-xs font-semibold">
                  {RSVP_LABELS[status]} ({count})
                </div>
                {list.length > 0 ? (
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {list.map((u) => (
                      <li key={u.id}>
                        {[u.first_name, u.last_name]
                          .filter(Boolean)
                          .join(' ') || u.email}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-xs text-muted-foreground">
                    No one yet
                  </div>
                )}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
