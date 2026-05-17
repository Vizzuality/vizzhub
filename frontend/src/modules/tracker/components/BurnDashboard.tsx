import { Card, CardContent } from '@/shared/components/ui/card';
import { cn } from '@/lib/utils';
import type { PeriodCostBreakdown } from '../types/tracker';
import { formatCurrency } from '../utils/constants';
import { useChartData } from '../utils/forecast';
import { CumulativeBurnCard } from './BurnDashboard/CumulativeBurnChart';

// Re-exports keep the historical public surface stable for both the
// page (`pages/ProjectTrackerDetail.tsx`) and the test suite.
export { computeChartYMax, computeEacCpi, useChartData } from '../utils/forecast';
export { MonthlyCostsChart } from './BurnDashboard/MonthlyCostsChart';

interface BurnDashboardProps {
  readonly periods: PeriodCostBreakdown[];
  readonly budget: number | null;
  readonly projectEndDate: string | null;
  /**
   * Manual progress as a fraction in [0, 1]. When null/0/1, the EVM forecast
   * is skipped (see `useChartData` for the precise edge-case handling).
   */
  readonly percentCompleted?: number | null;
}

const ACCENT_CLASSES: Record<string, string> = {
  green: 'bg-aux-neon-grass',
  red: 'bg-aux-red',
};

type KpiAccent = 'green' | 'red' | 'muted';

function KpiCard({
  label,
  value,
  sub,
  accent,
  dot = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly sub?: string;
  readonly accent?: KpiAccent;
  readonly dot?: boolean;
}): JSX.Element {
  const accentClass = accent ? ACCENT_CLASSES[accent] : undefined;

  return (
    <Card>
      <CardContent className="py-4 px-5">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">
          {label}
        </div>
        <div
          className={cn(
            'text-xl font-bold leading-tight flex items-center gap-2',
            accent === 'muted' && 'text-muted-foreground/50',
            (!accent || dot) && 'text-foreground',
            !dot && accent === 'green' && 'text-aux-neon-grass',
            !dot && accent === 'red' && 'text-aux-red',
          )}
        >
          {dot && accentClass && (
            <span
              className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', accentClass)}
            />
          )}
          {value}
        </div>
        {sub && (
          <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>
        )}
      </CardContent>
    </Card>
  );
}

function getVarianceAccent(variance: number | null): KpiAccent {
  if (variance == null) return 'muted';
  return variance >= 0 ? 'green' : 'red';
}

function getForecastSub(
  forecastFinal: number | null,
  budget: number | null,
): string | undefined {
  if (forecastFinal != null && budget != null) {
    return `${((forecastFinal / budget) * 100).toFixed(1)}% of budget`;
  }
  if (forecastFinal == null) return 'Needs end date';
  return undefined;
}

function getForecastAccent(
  forecastFinal: number | null,
  budget: number | null,
): KpiAccent | undefined {
  if (forecastFinal == null) return 'muted';
  if (budget != null && forecastFinal > budget) return 'red';
  return undefined;
}

function getVarianceSub(variance: number | null): string | undefined {
  if (variance == null) return undefined;
  return variance >= 0 ? 'Under budget' : 'Over budget';
}

export default function BurnDashboard({
  periods,
  budget,
  projectEndDate,
  percentCompleted = null,
}: BurnDashboardProps): JSX.Element | null {
  const { cumulative, totalBurn, forecastFinal, eacCpiFinal } = useChartData(
    periods,
    projectEndDate,
    { budget, percentCompleted },
  );

  if (periods.length === 0) return null;

  const budgetVariance = budget != null ? budget - totalBurn : null;

  return (
    <div className="space-y-4">
      {/* KPI Row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Budget"
          value={budget != null ? formatCurrency(budget) : '—'}
          accent={budget == null ? 'muted' : undefined}
        />
        <KpiCard
          label="Burn to Date"
          value={formatCurrency(totalBurn)}
          sub={budget != null ? `${((totalBurn / budget) * 100).toFixed(1)}% of budget` : undefined}
        />
        <KpiCard
          label="Forecast Final"
          value={forecastFinal != null ? formatCurrency(forecastFinal) : '—'}
          sub={getForecastSub(forecastFinal, budget)}
          accent={getForecastAccent(forecastFinal, budget)}
          dot
        />
        <KpiCard
          label="Variance"
          value={budgetVariance != null ? formatCurrency(budgetVariance) : '—'}
          sub={getVarianceSub(budgetVariance)}
          accent={getVarianceAccent(budgetVariance)}
          dot
        />
      </div>

      {/* Cumulative burn chart — always visible */}
      <CumulativeBurnCard data={cumulative} budget={budget} eacCpiFinal={eacCpiFinal} />
    </div>
  );
}
