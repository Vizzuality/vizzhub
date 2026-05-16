import { describe, it, expect } from 'vitest';
import { render, screen, renderHook } from '@testing-library/react';
import BurnDashboard, { computeChartYMax, computeEacCpi, useChartData } from '../BurnDashboard';
import type { PeriodCostBreakdown } from '../../types/tracker';

const periods: PeriodCostBreakdown[] = [
  {
    period_id: 'p1',
    date: '2026-01-01',
    staff_cost: 20_000,
    non_staff_cost: 0,
    total: 20_000,
    parts_count: 1,
  },
  {
    period_id: 'p2',
    date: '2026-02-01',
    staff_cost: 20_000,
    non_staff_cost: 0,
    total: 20_000,
    parts_count: 1,
  },
  {
    period_id: 'p3',
    date: '2026-03-01',
    staff_cost: 20_000,
    non_staff_cost: 0,
    total: 20_000,
    parts_count: 1,
  },
];

describe('computeEacCpi', () => {
  it('returns BAC / CPI = AC / percent_completed when inputs are valid', () => {
    // BAC=100000, AC=60000, percent_completed=0.4
    // CPI = (0.4 * 100000) / 60000 = 0.6667
    // EAC = 100000 / 0.6667 = 150000  ===  AC / pct = 60000 / 0.4
    expect(computeEacCpi(60_000, 100_000, 0.4)).toBe(150_000);
  });

  it('returns AC when percent_completed is 1.0 (project complete)', () => {
    expect(computeEacCpi(80_000, 100_000, 1.0)).toBe(80_000);
  });

  it('returns null when percent_completed is null', () => {
    expect(computeEacCpi(60_000, 100_000, null)).toBeNull();
  });

  it('returns null when percent_completed is 0', () => {
    expect(computeEacCpi(60_000, 100_000, 0)).toBeNull();
  });

  it('returns null when percent_completed is out of range (> 1)', () => {
    expect(computeEacCpi(60_000, 100_000, 1.5)).toBeNull();
  });

  it('returns null when budget is 0 or null', () => {
    expect(computeEacCpi(60_000, 0, 0.4)).toBeNull();
    expect(computeEacCpi(60_000, null, 0.4)).toBeNull();
  });

  it('returns null when AC (totalBurn) is 0', () => {
    expect(computeEacCpi(0, 100_000, 0.4)).toBeNull();
  });
});

describe('useChartData — EVM forecast', () => {
  it('exposes eacCpiFinal when budget and percent_completed are valid', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2026-06-01', {
        budget: 100_000,
        percentCompleted: 0.4,
      }),
    );
    // AC = 60k, pct = 0.4 → EAC = 150k
    expect(result.current.eacCpiFinal).toBe(150_000);
    // The chart series should carry the EVM endpoint at the last forecast point.
    const last = result.current.cumulative[result.current.cumulative.length - 1];
    expect(last.eacForecast).toBe(150_000);
  });

  it('eacCpiFinal is null when percent_completed is null', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2026-06-01', {
        budget: 100_000,
        percentCompleted: null,
      }),
    );
    expect(result.current.eacCpiFinal).toBeNull();
    expect(
      result.current.cumulative.every((p) => p.eacForecast === null),
    ).toBe(true);
  });

  it('eacCpiFinal is null when budget is null', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2026-06-01', {
        budget: null,
        percentCompleted: 0.4,
      }),
    );
    expect(result.current.eacCpiFinal).toBeNull();
  });

  it('preserves the existing time-trend forecast independently', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2026-06-01', {
        budget: 100_000,
        percentCompleted: null,
      }),
    );
    expect(result.current.forecastFinal).not.toBeNull();
    // The pace-based forecast still extends past last actuals.
    const hasForecastPoint = result.current.cumulative.some(
      (p) => p.forecast !== null,
    );
    expect(hasForecastPoint).toBe(true);
  });
});

describe('useChartData — forecast horizon (#40)', () => {
  it('produces a forecast point per remaining month with no 24-month cap', () => {
    // 3 actual months, project end 33 months past last actual → 33 forecast points.
    const { result } = renderHook(() =>
      useChartData(periods, '2028-12-01', { budget: null, percentCompleted: null }),
    );
    const forecastPoints = result.current.cumulative.filter((p) => p.forecast !== null);
    // The first forecast point is attached to the last actual (it carries the
    // seam value); the rest are pure-forecast points. Total = remainingMonths + 1.
    expect(forecastPoints.length).toBe(33 + 1);
  });

  it('forecastFinal matches the last cumulative forecast point on long horizons', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2028-12-01', { budget: null, percentCompleted: null }),
    );
    const last = result.current.cumulative[result.current.cumulative.length - 1];
    expect(last.forecast).toBe(result.current.forecastFinal);
  });

  it('emits no forecast points when project_end_date is in the past', () => {
    const { result } = renderHook(() =>
      useChartData(periods, '2025-06-01', { budget: null, percentCompleted: null }),
    );
    const forecastPoints = result.current.cumulative.filter((p) => p.forecast !== null);
    expect(forecastPoints.length).toBe(0);
    expect(result.current.forecastFinal).toBe(result.current.totalBurn);
  });

  it('emits no forecast points when project_end_date is null', () => {
    const { result } = renderHook(() =>
      useChartData(periods, null, { budget: null, percentCompleted: null }),
    );
    const forecastPoints = result.current.cumulative.filter((p) => p.forecast !== null);
    expect(forecastPoints.length).toBe(0);
    expect(result.current.forecastFinal).toBeNull();
  });
});

describe('computeChartYMax', () => {
  const sampleData = [
    { cumulative: 50_000, forecast: null, eacForecast: null },
    { cumulative: 100_000, forecast: 100_000, eacForecast: 100_000 },
    { cumulative: 0, forecast: 120_000, eacForecast: 150_000 },
  ];

  it('includes the EAC endpoint when it fits naturally below 3 × budget', () => {
    const budget = 200_000;
    const eac = 150_000;
    const ymax = computeChartYMax(sampleData, budget, eac);
    // Natural max = max(actuals 100k, forecast 120k, budget 200k, eac 150k) = 200k.
    expect(ymax).toBe(Math.ceil(200_000 * 1.15));
  });

  it('clamps Y max to 3 × budget when EAC blows past it (extreme overrun)', () => {
    // Real case: AC=162k, pct=5% → EAC=3.24M. Budget=1M → 3×budget=3M.
    const data = [
      { cumulative: 162_000, forecast: null, eacForecast: null },
      { cumulative: 0, forecast: 200_000, eacForecast: 3_240_000 },
    ];
    const budget = 1_000_000;
    const eac = 3_240_000;
    const ymax = computeChartYMax(data, budget, eac);
    expect(ymax).toBe(Math.ceil(3 * budget * 1.15));
    // And it must not equal the natural-EAC value.
    expect(ymax).toBeLessThan(Math.ceil(eac * 1.15));
  });

  it('falls back to natural max when there is no budget', () => {
    const ymax = computeChartYMax(sampleData, null, 150_000);
    // No budget → no clamp; natural max = max(100k, 120k, 150k) = 150k.
    expect(ymax).toBe(Math.ceil(150_000 * 1.15));
  });

  it('ignores EAC when it is null', () => {
    const ymax = computeChartYMax(sampleData, 200_000, null);
    expect(ymax).toBe(Math.ceil(200_000 * 1.15));
  });

  it('does not clamp when EAC sits exactly at 3 × budget', () => {
    const data = [{ cumulative: 100_000, forecast: null, eacForecast: 300_000 }];
    const ymax = computeChartYMax(data, 100_000, 300_000);
    // 3 × budget = 300k, EAC = 300k → not greater than 3 × budget, no clamp.
    expect(ymax).toBe(Math.ceil(300_000 * 1.15));
  });
});

describe('BurnDashboard — EVM forecast legend', () => {
  it('renders the EVM legend entry when percent_completed is provided', () => {
    render(
      <BurnDashboard
        periods={periods}
        budget={100_000}
        projectEndDate="2026-06-01"
        percentCompleted={0.4}
      />,
    );
    expect(
      screen.getByText('Forecast (current efficiency)'),
    ).toBeInTheDocument();
    expect(screen.getByText('Forecast (current pace)')).toBeInTheDocument();
  });

  it('omits the EVM legend entry when percent_completed is null', () => {
    render(
      <BurnDashboard
        periods={periods}
        budget={100_000}
        projectEndDate="2026-06-01"
        percentCompleted={null}
      />,
    );
    expect(
      screen.queryByText('Forecast (current efficiency)'),
    ).not.toBeInTheDocument();
    // Pace-based forecast must still render.
    expect(screen.getByText('Forecast (current pace)')).toBeInTheDocument();
  });

  it('omits the EVM legend entry when percent_completed is 0', () => {
    render(
      <BurnDashboard
        periods={periods}
        budget={100_000}
        projectEndDate="2026-06-01"
        percentCompleted={0}
      />,
    );
    expect(
      screen.queryByText('Forecast (current efficiency)'),
    ).not.toBeInTheDocument();
  });

  it('omits the EVM legend entry when budget is null', () => {
    render(
      <BurnDashboard
        periods={periods}
        budget={null}
        projectEndDate="2026-06-01"
        percentCompleted={0.4}
      />,
    );
    expect(
      screen.queryByText('Forecast (current efficiency)'),
    ).not.toBeInTheDocument();
  });

  it('renders the (i) info trigger next to the chart title', () => {
    render(
      <BurnDashboard
        periods={periods}
        budget={100_000}
        projectEndDate="2026-06-01"
        percentCompleted={0.4}
      />,
    );
    expect(
      screen.getByRole('button', { name: /about the forecasts/i }),
    ).toBeInTheDocument();
  });
});
