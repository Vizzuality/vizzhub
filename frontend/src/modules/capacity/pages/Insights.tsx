import { useUrlState } from '@/shared/hooks/useUrlState';
import { useCapacityInsights } from '@/modules/capacity/hooks/useCapacityInsights';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';

function defaultRange(): { start: string; end: string } {
  const now = new Date();
  const endYear = now.getFullYear();
  const endMonth = now.getMonth() + 1;
  const startDate = new Date(endYear, endMonth - 7, 1);
  const startYear = startDate.getFullYear();
  const startMonth = startDate.getMonth() + 1;
  return {
    start: `${startYear}-${String(startMonth).padStart(2, '0')}`,
    end: `${endYear}-${String(endMonth).padStart(2, '0')}`,
  };
}

const defaults = defaultRange();

export default function Insights(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: defaults.start },
    end: { defaultValue: defaults.end },
  });

  const { data, isLoading, error } = useCapacityInsights(state.start, state.end);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Capacity Insights</h1>
        <MonthRangePicker
          startDate={state.start}
          endDate={state.end}
          onChange={(start, end) => setState({ start, end })}
        />
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load capacity data
        </div>
      )}

      {data && <InsightsChart data={data} />}
    </div>
  );
}
