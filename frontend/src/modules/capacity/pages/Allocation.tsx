import { useMemo } from 'react';
import { ArrowDownWideNarrow, ArrowUpNarrowWide } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useAllocationUsers } from '@/modules/capacity/hooks/useAllocationUsers';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { Button } from '@/shared/components/ui/button';

const fmtMonth = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;

function defaultRange(): { start: string; end: string } {
  const now = new Date();
  const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const month = fmtMonth(lastMonth);
  return { start: month, end: month };
}

const defaults = defaultRange();

function formatPeriodsHeader(periods: string[]): string {
  if (periods.length === 0) return '';
  let lastYear = '';
  const parts: string[] = [];
  for (const p of periods) {
    const [year, month] = p.split('-');
    const date = new Date(Number(year), Number(month) - 1);
    const monthName = date.toLocaleDateString('en', { month: 'short' });
    if (year !== lastYear) {
      parts.push(`${monthName} ${year}`);
      lastYear = year;
    } else {
      parts.push(monthName);
    }
  }
  return `Based on ${parts.join(', ')}`;
}

export default function Allocation(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: defaults.start },
    end: { defaultValue: defaults.end },
    sort: { defaultValue: 'desc' },
  });

  const { data, isLoading, error } = useAllocationUsers(state.start, state.end);
  const isAsc = state.sort === 'asc';

  const sortedUsers = useMemo(() => {
    if (!data) return [];
    return isAsc ? [...data.users].reverse() : data.users;
  }, [data, isAsc]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-2xl font-semibold">Team Allocation</h1>
          {data && data.periods_used.length > 0 && (
            <span className="text-muted-foreground text-sm">
              {formatPeriodsHeader(data.periods_used)}
            </span>
          )}
        </div>
        <div className="flex items-end gap-4">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setState({ sort: isAsc ? 'desc' : 'asc' })}
            title={isAsc ? 'Sort descending' : 'Sort ascending'}
          >
            {isAsc ? (
              <ArrowUpNarrowWide className="h-4 w-4" />
            ) : (
              <ArrowDownWideNarrow className="h-4 w-4" />
            )}
          </Button>
          <MonthRangePicker
            startDate={state.start}
            endDate={state.end}
            onChange={(start, end) => setState({ start, end })}
            idPrefix="allocation-"
          />
        </div>
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load allocation data
        </div>
      )}

      {data && <UserAllocationList users={sortedUsers} />}
    </div>
  );
}
