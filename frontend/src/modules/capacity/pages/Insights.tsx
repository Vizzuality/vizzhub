import { useCallback, useRef } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useCapacityInsights } from '@/modules/capacity/hooks/useCapacityInsights';
import { useCapacityFADetail } from '@/modules/capacity/hooks/useCapacityFADetail';
import { useCapacityUserDetail } from '@/modules/capacity/hooks/useCapacityUserDetail';
import { useReportableUsers } from '@/modules/capacity/hooks/useReportableUsers';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import { FADetailChart } from '@/modules/capacity/components/FADetailChart';
import { UserDetailChart } from '@/modules/capacity/components/UserDetailChart';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';

const fmtMonth = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;

function defaultRange(monthsBack: number): { start: string; end: string } {
  const safeEnd = new Date(Date.now() - 45 * 86_400_000);
  const endDate = new Date(safeEnd.getFullYear(), safeEnd.getMonth(), 1);
  const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - monthsBack, 1);
  return { start: fmtMonth(startDate), end: fmtMonth(endDate) };
}

const overviewDefaults = defaultRange(5);
const detailDefaults = defaultRange(2);
const userDetailDefaults = defaultRange(5);

export default function Insights(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: overviewDefaults.start },
    end: { defaultValue: overviewDefaults.end },
    fa: { defaultValue: 'FE' },
    detail_start: { defaultValue: detailDefaults.start },
    detail_end: { defaultValue: detailDefaults.end },
    user_id: { defaultValue: '' },
    user_start: { defaultValue: userDetailDefaults.start },
    user_end: { defaultValue: userDetailDefaults.end },
  });

  const detailRef = useRef<HTMLDivElement>(null);
  const userDetailRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useCapacityInsights(state.start, state.end);
  const {
    data: detailData,
    isLoading: detailLoading,
    error: detailError,
  } = useCapacityFADetail(state.fa, state.detail_start, state.detail_end);
  const { data: reportableUsers } = useReportableUsers();
  const {
    data: userDetailData,
    isLoading: userDetailLoading,
    error: userDetailError,
  } = useCapacityUserDetail(state.user_id, state.user_start, state.user_end);

  const handleBarClick = useCallback((fa: string, period: string): void => {
    const [year, month] = period.split('-').map(Number);
    const clickedDate = new Date(year, month - 1, 1);
    const startDate = new Date(clickedDate.getFullYear(), clickedDate.getMonth() - 1, 1);
    const endDate = new Date(clickedDate.getFullYear(), clickedDate.getMonth() + 1, 1);
    setState({
      fa,
      detail_start: fmtMonth(startDate),
      detail_end: fmtMonth(endDate),
    });
    detailRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [setState]);

  const handleUserClick = useCallback((userId: string): void => {
    setState({ user_id: userId });
    userDetailRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [setState]);

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

      {data && (
        <section className="rounded-xl border bg-card p-5">
          <InsightsChart
            key={`${state.start}-${state.end}`}
            data={data}
            onBarClick={handleBarClick}
          />
        </section>
      )}

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
          <section className="rounded-xl border bg-card p-5">
            <FADetailChart
              key={`${state.fa}-${state.detail_start}-${state.detail_end}`}
              data={detailData}
              fa={state.fa}
              onFAChange={(fa) => setState({ fa })}
              startDate={state.detail_start}
              endDate={state.detail_end}
              onRangeChange={(detail_start, detail_end) =>
                setState({ detail_start, detail_end })
              }
              onUserClick={handleUserClick}
            />
          </section>
        )}
      </div>

      <div ref={userDetailRef}>
        {userDetailLoading && (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            Loading...
          </div>
        )}

        {userDetailError && (
          <div className="flex h-64 items-center justify-center text-destructive">
            Failed to load user detail data
          </div>
        )}

        {reportableUsers && (
          <section className="rounded-xl border bg-card p-5">
            <UserDetailChart
              key={`${state.user_id}-${state.user_start}-${state.user_end}`}
              data={userDetailData ?? []}
              userId={state.user_id}
              users={reportableUsers}
              onUserChange={(user_id) => setState({ user_id })}
              startDate={state.user_start}
              endDate={state.user_end}
              onRangeChange={(user_start, user_end) =>
                setState({ user_start, user_end })
              }
            />
          </section>
        )}
      </div>
    </div>
  );
}
