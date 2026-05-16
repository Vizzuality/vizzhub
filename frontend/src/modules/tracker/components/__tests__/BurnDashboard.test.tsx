import { describe, it, expect } from 'vitest';
import { render, screen, renderHook } from '@testing-library/react';
import BurnDashboard, { computeEacCpi, useChartData } from '../BurnDashboard';
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
