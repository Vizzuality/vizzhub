import { useMemo } from 'react';
import type { PeriodCostBreakdown } from '../types/tracker';
import { shortMonth } from './constants';

export interface CumulativePoint {
  date: string;
  label: string;
  cumulative: number | null;
  forecast: number | null;
  eacForecast: number | null;
  /**
   * Set only on the EAC line's terminal point so a stable, module-level
   * label component can render the real (unclamped) projection without
   * closure access to component state.
   */
  eacEndValue?: number;
}

export interface MonthlyPoint {
  date: string;
  label: string;
  staff: number;
  nonStaff: number;
  total: number;
}

export function monthsBetween(from: Date, to: Date): number {
  return (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth());
}

export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value.toFixed(0)}`;
}

/**
 * Weighted moving average: recent months weigh more.
 * Last 3 months get weights 3, 2, 1; older months get weight 1.
 * Falls back to simple average with fewer than 2 data points.
 */
export function weightedMonthlyAvg(monthlyCosts: number[]): number {
  const n = monthlyCosts.length;
  if (n === 0) return 0;
  if (n === 1) return monthlyCosts[0];

  const RECENT_WINDOW = 3;
  let weightedSum = 0;
  let totalWeight = 0;

  for (let i = 0; i < n; i++) {
    const distFromEnd = n - 1 - i;
    const weight = distFromEnd < RECENT_WINDOW ? RECENT_WINDOW - distFromEnd : 1;
    weightedSum += monthlyCosts[i] * weight;
    totalWeight += weight;
  }

  return weightedSum / totalWeight;
}

/**
 * Compute the chart's Y-axis maximum so that all rendered series participate
 * in the auto-fit, with an upper clamp on extreme overruns.
 *
 * On projects with low percent_completed, EAC_CPI = AC / percent_completed can
 * dwarf the budget and actuals (e.g. AC=€162k, pct=5% → EAC=€3.24M). Without a
 * clamp, the actual-cost area gets crushed against the X-axis; without
 * including EAC at all, the forecast line is drawn outside the visible box.
 *
 * Strategy: use the natural max of (actuals + budget + time-trend forecast +
 * EAC), then if EAC drives the max above 3 × budget, clamp at 3 × budget. The
 * end-of-line label still surfaces the real EAC value to the user.
 */
export function computeChartYMax(
  data: ReadonlyArray<{ cumulative: number | null; forecast: number | null; eacForecast: number | null }>,
  budget: number | null,
  eacCpiFinal: number | null,
): number {
  const baseMax = Math.max(
    ...data.map((d) => Math.max(d.cumulative ?? 0, d.forecast ?? 0)),
    budget ?? 0,
  );
  const naturalMax = Math.max(baseMax, eacCpiFinal ?? 0);
  if (
    budget != null &&
    budget > 0 &&
    eacCpiFinal != null &&
    eacCpiFinal > 3 * budget
  ) {
    return Math.ceil(Math.max(baseMax, 3 * budget) * 1.15);
  }
  return Math.ceil(naturalMax * 1.15);
}

function buildForecastPoints(
  lastDate: Date,
  totalBurn: number,
  weightedAvg: number,
  remainingMonths: number,
): { forecastFinal: number; points: CumulativePoint[] } {
  const forecastFinal = Math.round((totalBurn + weightedAvg * remainingMonths) * 100) / 100;
  const points: CumulativePoint[] = [];
  let fcum = totalBurn;

  for (let i = 1; i <= remainingMonths; i++) {
    const fDate = new Date(lastDate);
    fDate.setMonth(fDate.getMonth() + i);
    fcum += weightedAvg;
    points.push({
      date: fDate.toISOString().slice(0, 10),
      label: shortMonth(fDate.toISOString().slice(0, 10)),
      // null (not 0) so the Actual area stops at the last reported month —
      // Recharts breaks the line on null with connectNulls={false}.
      cumulative: null,
      forecast: Math.round(fcum * 100) / 100,
      eacForecast: null,
    });
  }

  return { forecastFinal, points };
}

/**
 * Append forecast points to the cumulative series in place, optionally
 * overlaying a linearly-interpolated EAC line on top of them. Returns
 * `forecastFinal` (the time-trend projection) or null when forecasting
 * cannot be applied for the given inputs.
 */
function applyForecast(
  cumWithForecast: CumulativePoint[],
  cumulativeActual: CumulativePoint[],
  projectEndDate: string,
  lastSortedDate: string,
  totalBurn: number,
  weightedAvg: number,
  eacCpiFinal: number | null,
): number | null {
  const lastDate = new Date(lastSortedDate + 'T00:00:00');
  const remainingMonths = monthsBetween(lastDate, new Date(projectEndDate + 'T00:00:00'));

  if (remainingMonths <= 0) {
    return totalBurn;
  }

  const forecast = buildForecastPoints(lastDate, totalBurn, weightedAvg, remainingMonths);

  const lastActual = cumulativeActual[cumulativeActual.length - 1];
  cumWithForecast[cumWithForecast.length - 1] = {
    ...lastActual,
    forecast: lastActual.cumulative,
    eacForecast: eacCpiFinal != null ? lastActual.cumulative : null,
  };
  cumWithForecast.push(...forecast.points);

  if (eacCpiFinal != null) {
    applyEacInterpolation(cumWithForecast, forecast.points.length, totalBurn, eacCpiFinal);
  }
  return forecast.forecastFinal;
}

/**
 * Linearly interpolate the EAC straight-line over the forecast tail so the
 * segment renders cleanly without relying on connectNulls between distant
 * points.
 */
function applyEacInterpolation(
  cumWithForecast: CumulativePoint[],
  forecastCount: number,
  totalBurn: number,
  eacCpiFinal: number,
): void {
  const slope = (eacCpiFinal - totalBurn) / forecastCount;
  const startIdx = cumWithForecast.length - forecastCount;
  for (let i = 0; i < forecastCount; i++) {
    const interp = totalBurn + slope * (i + 1);
    cumWithForecast[startIdx + i] = {
      ...cumWithForecast[startIdx + i],
      eacForecast: Math.round(interp * 100) / 100,
    };
  }
  // Tag the terminal forecast point with the unclamped EAC so the label
  // component (which lives outside the parent component) can render the
  // real value without reading closure state.
  const endIdx = cumWithForecast.length - 1;
  cumWithForecast[endIdx] = { ...cumWithForecast[endIdx], eacEndValue: eacCpiFinal };
}

/**
 * EVM-standard Estimate at Completion using the CPI method:
 *   EAC_CPI = BAC / CPI  where  CPI = EV / AC = (% complete × BAC) / AC
 *           = AC / % complete
 *
 * Returns null when any input is missing or out of range — projects
 * with no progress reported, zero spend, or no budget cannot produce
 * a meaningful EVM projection.
 */
export function computeEacCpi(
  totalBurn: number,
  budget: number | null,
  percentCompleted: number | null | undefined,
): number | null {
  if (budget == null || budget <= 0) return null;
  if (totalBurn <= 0) return null;
  if (percentCompleted == null) return null;
  if (percentCompleted <= 0 || percentCompleted > 1) return null;
  return Math.round((totalBurn / percentCompleted) * 100) / 100;
}

export function useChartData(
  periods: PeriodCostBreakdown[],
  projectEndDate: string | null,
  options?: { budget?: number | null; percentCompleted?: number | null },
): {
  cumulative: CumulativePoint[];
  monthly: MonthlyPoint[];
  totalBurn: number;
  forecastFinal: number | null;
  eacCpiFinal: number | null;
  avgMonthlyBurn: number;
} {
  const budget = options?.budget ?? null;
  const percentCompleted = options?.percentCompleted ?? null;

  return useMemo(() => {
    const sorted = [...periods].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );

    let cum = 0;
    const cumulativeActual: CumulativePoint[] = sorted.map((p) => {
      cum += p.total;
      return {
        date: p.date,
        label: shortMonth(p.date),
        cumulative: Math.round(cum * 100) / 100,
        forecast: null,
        eacForecast: null,
      };
    });

    const monthly: MonthlyPoint[] = sorted.map((p) => ({
      date: p.date,
      label: shortMonth(p.date),
      staff: p.staff_cost,
      nonStaff: p.non_staff_cost,
      total: p.total,
    }));

    const totalBurn = cum;
    const monthCount = sorted.length;
    const avgMonthlyBurn = monthCount > 0 ? totalBurn / monthCount : 0;

    const monthlyCosts = sorted.map((p) => p.total);
    const weightedAvg = weightedMonthlyAvg(monthlyCosts);

    const eacCpiFinal = computeEacCpi(totalBurn, budget, percentCompleted);
    const cumWithForecast = [...cumulativeActual];

    const forecastFinal =
      projectEndDate && monthCount > 0
        ? applyForecast(
            cumWithForecast,
            cumulativeActual,
            projectEndDate,
            sorted[sorted.length - 1].date,
            totalBurn,
            weightedAvg,
            eacCpiFinal,
          )
        : null;

    return {
      cumulative: cumWithForecast,
      monthly,
      totalBurn,
      forecastFinal,
      eacCpiFinal,
      avgMonthlyBurn,
    };
  }, [periods, projectEndDate, budget, percentCompleted]);
}
