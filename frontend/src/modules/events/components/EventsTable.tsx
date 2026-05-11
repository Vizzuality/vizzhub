import { ArrowUp, ArrowDown } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { StarRating } from './StarRating';
import { AttendingIndicator } from './AttendingIndicator';
import type { EventSummary } from '../types/events';

type SortKey = 'name' | 'start_date' | 'total_cost' | 'rating';
type SortDir = 'asc' | 'desc';

interface EventsTableProps {
  readonly events: EventSummary[];
  readonly onRowClick: (id: string) => void;
  readonly sortKey: SortKey | string;
  readonly sortDir: SortDir;
  readonly onSortChange: (key: SortKey, dir: SortDir) => void;
}

function SortIcon({
  active,
  dir,
}: {
  active: boolean;
  dir: SortDir;
}): JSX.Element | null {
  if (!active) return null;
  return dir === 'asc' ? (
    <ArrowUp className="inline h-3 w-3 ml-1" />
  ) : (
    <ArrowDown className="inline h-3 w-3 ml-1" />
  );
}

function SortableHead({
  label,
  colKey,
  current,
  dir,
  onSortChange,
}: {
  label: string;
  colKey: SortKey;
  current: string;
  dir: SortDir;
  onSortChange: (k: SortKey, d: SortDir) => void;
}): JSX.Element {
  const active = current === colKey;
  return (
    <TableHead
      className="cursor-pointer select-none"
      onClick={() =>
        onSortChange(colKey, active && dir === 'desc' ? 'asc' : 'desc')
      }
    >
      {label}
      <SortIcon active={active} dir={dir} />
    </TableHead>
  );
}

export function EventsTable({
  events,
  onRowClick,
  sortKey,
  sortDir,
  onSortChange,
}: EventsTableProps): JSX.Element {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHead
              label="Name"
              colKey="name"
              current={sortKey}
              dir={sortDir}
              onSortChange={onSortChange}
            />
            <TableHead>Type</TableHead>
            <TableHead>Theme</TableHead>
            <TableHead>Region</TableHead>
            <SortableHead
              label="Start"
              colKey="start_date"
              current={sortKey}
              dir={sortDir}
              onSortChange={onSortChange}
            />
            <TableHead>Location</TableHead>
            <TableHead>Attending</TableHead>
            <SortableHead
              label="Total cost"
              colKey="total_cost"
              current={sortKey}
              dir={sortDir}
              onSortChange={onSortChange}
            />
            <TableHead>Attendees</TableHead>
            <SortableHead
              label="Rating"
              colKey="rating"
              current={sortKey}
              dir={sortDir}
              onSortChange={onSortChange}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((e) => (
            <TableRow
              key={e.id}
              className="cursor-pointer hover:bg-muted/30"
              onClick={() => onRowClick(e.id)}
            >
              <TableCell className="font-medium">{e.name}</TableCell>
              <TableCell>{e.event_type}</TableCell>
              <TableCell>{e.theme_primary}</TableCell>
              <TableCell>{e.region_focus}</TableCell>
              <TableCell>{e.start_date}</TableCell>
              <TableCell>
                {[e.location_city, e.location_country]
                  .filter(Boolean)
                  .join(' · ') || '—'}
              </TableCell>
              <TableCell>
                {e.attending ? <AttendingIndicator value={e.attending} /> : '—'}
              </TableCell>
              <TableCell>€{Number(e.total_cost).toFixed(2)}</TableCell>
              <TableCell>{e.attendee_count}</TableCell>
              <TableCell>
                {e.rating != null ? (
                  <StarRating
                    value={e.rating}
                    onChange={() => {}}
                    size={14}
                  />
                ) : (
                  '—'
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
