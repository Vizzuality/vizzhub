import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { YtdBurnupChart } from '../YtdBurnupChart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

const MONTHS: DashboardMonth[] = Array.from({ length: 12 }, (_, i) => ({
  month: i + 1,
  amount_eur: 1000,
  status: i < 4 ? 'closed' : 'open',
}));

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
});
