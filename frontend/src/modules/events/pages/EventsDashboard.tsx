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
import { AttendingFilterSelect } from '../components/AttendingFilterSelect';
import { StatsCharts } from '../components/StatsCharts';
import { useEventStats } from '../hooks/useEventStats';
import { useEventOptions } from '../hooks/useEventOptions';
import { ALL_SENTINEL, buildYearOptions } from '../utils/constants';
import type { AttendingFilter, EventStats } from '../types/events';

const urlSchema = {
  year: { defaultValue: '' },
  attending: { defaultValue: '' },
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
  const { data: options } = useEventOptions();
  const yearOptions = useMemo(
    () => buildYearOptions(options?.years_with_data ?? [], state.year || undefined),
    [options?.years_with_data, state.year],
  );

  const { data: stats, isLoading } = useEventStats({
    ...(state.year && { year: Number(state.year) }),
    ...(state.attending && { attending: state.attending as AttendingFilter }),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Events Dashboard</h1>
        <div className="flex items-center gap-3">
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
          <AttendingFilterSelect
            value={state.attending}
            onChange={(v) => setState({ attending: v })}
          />
        </div>
      </div>

      {renderStatsContent(isLoading, stats)}
    </div>
  );
}
