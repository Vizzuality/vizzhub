import { useMemo } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { StatsCharts } from '../components/StatsCharts';
import { useEventStats } from '../hooks/useEventStats';
import { ALL_SENTINEL, buildYearOptions } from '../utils/constants';
import type { EventStats } from '../types/events';

const urlSchema = {
  year: { defaultValue: '' },
};

function renderStatsContent(
  isLoading: boolean,
  stats: EventStats | undefined,
): JSX.Element | null {
  if (isLoading) return <LoadingSpinner />;
  if (stats) return <StatsCharts stats={stats} />;
  return null;
}

export default function EventsDashboard(): JSX.Element {
  const { state, setState } = useUrlState(urlSchema);
  const yearOptions = useMemo(() => buildYearOptions(), []);

  const { data: stats, isLoading } = useEventStats(
    state.year ? Number(state.year) : undefined,
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Events Dashboard</h1>
        <Select
          value={state.year || ALL_SENTINEL}
          onValueChange={(v) => setState({ year: v === ALL_SENTINEL ? '' : v })}
        >
          <SelectTrigger className="w-[130px] h-9 text-sm">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All Years</SelectItem>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={y}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {renderStatsContent(isLoading, stats)}
    </div>
  );
}
