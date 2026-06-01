import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { YtdBurnupChart, buildBurnupSeries } from '../YtdBurnupChart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

const MONTHS: DashboardMonth[] = Array.from({ length: 12 }, (_, i) => ({
  month: i + 1,
  amount_eur: 1000,
  status: i < 4 ? 'recognized' : 'forecast',
  prev_amount_eur: 800,
}));

const MONTHS_NO_PRIOR: DashboardMonth[] = MONTHS.map((m) => ({ ...m, prev_amount_eur: 0 }));

describe('buildBurnupSeries', () => {
  it('plan accumulates every month up to the year total', () => {
    const series = buildBurnupSeries(MONTHS);
    expect(series.map((p) => p.plan)).toEqual([
      1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000,
    ]);
    expect(series[11].plan).toBe(12000); // year total
  });

  it('recognized advances only on recognized months, then plateaus', () => {
    const series = buildBurnupSeries(MONTHS);
    expect(series.map((p) => p.recognized)).toEqual([
      1000, 2000, 3000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000, 4000,
    ]);
  });

  it('prevYear accumulates the prior-year amount every month (full reference curve)', () => {
    const series = buildBurnupSeries(MONTHS);
    expect(series.map((p) => p.prevYear)).toEqual([
      800, 1600, 2400, 3200, 4000, 4800, 5600, 6400, 7200, 8000, 8800, 9600,
    ]);
  });
});

describe('YtdBurnupChart', () => {
  it('renders the cumulative area path', () => {
    const { container } = render(
      <div style={{ width: 800, height: 400 }}>
        <YtdBurnupChart months={MONTHS} />
      </div>,
    );
    const areas = container.querySelectorAll('.recharts-area-area, .recharts-area-curve');
    expect(areas.length).toBeGreaterThan(0);
  });

  it('draws the prior-year reference line when prior-year data exists', () => {
    const { container } = render(
      <div style={{ width: 800, height: 400 }}>
        <YtdBurnupChart months={MONTHS} />
      </div>,
    );
    // Two Line series (plan + prior year) → two line curves.
    const lines = container.querySelectorAll('.recharts-line-curve');
    expect(lines.length).toBe(2);
  });

  it('omits the prior-year line when there is no prior-year data', () => {
    const { container } = render(
      <div style={{ width: 800, height: 400 }}>
        <YtdBurnupChart months={MONTHS_NO_PRIOR} />
      </div>,
    );
    // Only the plan line remains.
    const lines = container.querySelectorAll('.recharts-line-curve');
    expect(lines.length).toBe(1);
  });
});
