import { useMemo } from 'react';
import { ArrowDownWideNarrow, ArrowUpNarrowWide } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useAllocationUsers } from '@/modules/capacity/hooks/useAllocationUsers';
import { useAllocationProjects } from '@/modules/capacity/hooks/useAllocationProjects';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';
import { ProjectAllocationList } from '@/modules/capacity/components/ProjectAllocationList';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FA_ORDER } from '@/modules/capacity/utils/constants';

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
    fa: { defaultValue: 'all' },
  });

  const { data, isLoading, error } = useAllocationUsers(state.start, state.end);
  const {
    data: projectsData,
    isLoading: projectsLoading,
    error: projectsError,
  } = useAllocationProjects(state.start, state.end);
  const isAsc = state.sort === 'asc';

  const filteredUsers = useMemo(() => {
    if (!data) return [];
    let users = data.users;
    if (state.fa !== 'all') {
      users = users.filter((u) => u.functional_area === state.fa);
    }
    return isAsc ? [...users].reverse() : users;
  }, [data, isAsc, state.fa]);

  const sortedProjects = useMemo(() => {
    if (!projectsData) return [];
    return isAsc ? [...projectsData.projects].reverse() : projectsData.projects;
  }, [projectsData, isAsc]);

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
          <Select value={state.fa} onValueChange={(fa) => setState({ fa })}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All FAs</SelectItem>
              {FA_ORDER.map((fa) => (
                <SelectItem key={fa} value={fa}>
                  {fa}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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

      {data && <UserAllocationList users={filteredUsers} />}

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-xl font-semibold">Project Distribution</h2>
        {projectsData && projectsData.periods_used.length > 0 && (
          <span className="text-muted-foreground text-sm">
            {formatPeriodsHeader(projectsData.periods_used)}
          </span>
        )}
      </div>

      {projectsLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {projectsError && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load project data
        </div>
      )}

      {projectsData && <ProjectAllocationList projects={sortedProjects} />}
    </div>
  );
}
