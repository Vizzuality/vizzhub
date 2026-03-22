import { useRef } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useCapacityInsights } from '@/modules/capacity/hooks/useCapacityInsights';
import { useCapacityFADetail } from '@/modules/capacity/hooks/useCapacityFADetail';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import { FADetailChart } from '@/modules/capacity/components/FADetailChart';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';

function defaultOverviewRange(): { start: string; end: string } {
  const now = new Date();
  const endDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - 5, 1);
  const fmt = (d: Date): string =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { start: fmt(startDate), end: fmt(endDate) };
}

function defaultDetailRange(): { detail_start: string; detail_end: string } {
  const now = new Date();
  const endDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - 2, 1);
  const fmt = (d: Date): string =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { detail_start: fmt(startDate), detail_end: fmt(endDate) };
}

const overviewDefaults = defaultOverviewRange();
const detailDefaults = defaultDetailRange();

export default function Insights(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: overviewDefaults.start },
    end: { defaultValue: overviewDefaults.end },
    fa: { defaultValue: 'FE' },
    detail_start: { defaultValue: detailDefaults.detail_start },
    detail_end: { defaultValue: detailDefaults.detail_end },
  });

  const detailRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useCapacityInsights(state.start, state.end);
  const {
    data: detailData,
    isLoading: detailLoading,
    error: detailError,
  } = useCapacityFADetail(state.fa, state.detail_start, state.detail_end);

  const handleBarClick = (fa: string, period: string): void => {
    setState({ fa, detail_start: period, detail_end: period });
    detailRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Capacity Insights</h1>
        <MonthRangePicker
          startDate={state.start}
          endDate={state.end}
          onChange={(start, end) => setState({ start, end })}
          idPrefix="overview-"
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

      {data && <InsightsChart data={data} onBarClick={handleBarClick} />}

      <div ref={detailRef}>
        {detailLoading && (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            Loading...
          </div>
        )}

        {detailError && (
          <div className="flex h-64 items-center justify-center text-destructive">
            Failed to load detail data
          </div>
        )}

        {detailData && (
          <FADetailChart
            data={detailData}
            fa={state.fa}
            onFAChange={(fa) => setState({ fa })}
            startDate={state.detail_start}
            endDate={state.detail_end}
            onRangeChange={(detail_start, detail_end) =>
              setState({ detail_start, detail_end })
            }
          />
        )}
      </div>
    </div>
  );
}
