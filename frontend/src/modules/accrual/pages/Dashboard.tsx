import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useAccrualDashboard } from '@/modules/accrual/hooks/useAccrualDashboard';
import { DashboardKpis } from '@/modules/accrual/components/DashboardKpis';
import { RecognitionByMonthChart } from '@/modules/accrual/components/RecognitionByMonthChart';
import { YtdBurnupChart } from '@/modules/accrual/components/YtdBurnupChart';

const CURRENT_YEAR = new Date().getFullYear();

const urlSchema = {
  year: { defaultValue: CURRENT_YEAR },
};

export function AccrualDashboard(): JSX.Element {
  const { state, setState } = useUrlState(urlSchema);
  const year = state.year;
  const { data, isLoading } = useAccrualDashboard(year);
  const years = data?.available_years ?? [];
  const minYear = years.length ? years[0] : year;
  const maxYear = years.length ? years[years.length - 1] : year;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual Dashboard</h1>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label="previous year"
            disabled={year <= minYear}
            onClick={() => setState({ year: year - 1 })}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span
            data-testid="accrual-dashboard-year"
            className="w-14 text-center font-medium"
          >
            {year}
          </span>
          <Button
            variant="outline"
            size="icon"
            aria-label="next year"
            disabled={year >= maxYear}
            onClick={() => setState({ year: year + 1 })}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {isLoading || !data ? (
        <LoadingSpinner />
      ) : (
        <>
          <DashboardKpis kpis={data.kpis} />
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border p-4">
              <h2 className="mb-2 text-sm font-medium text-muted-foreground">
                Recognition by month
              </h2>
              <RecognitionByMonthChart months={data.months} />
            </div>
            <div className="rounded-lg border p-4">
              <h2 className="mb-2 text-sm font-medium text-muted-foreground">
                YTD burn-up vs year plan
              </h2>
              <YtdBurnupChart months={data.months} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
