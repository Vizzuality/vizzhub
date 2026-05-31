import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RecognitionByMonthChart } from '../RecognitionByMonthChart';
import type { DashboardMonth } from '@/modules/accrual/types/accrual';

const MONTHS: DashboardMonth[] = Array.from({ length: 12 }, (_, i) => ({
  month: i + 1,
  amount_eur: i < 3 ? 1000 : 500,
  status: i < 3 ? 'closed' : 'open',
}));

describe('RecognitionByMonthChart', () => {
  it('renders bar rectangles for the months with data', () => {
    const { container } = render(
      <div style={{ width: 800, height: 400 }}>
        <RecognitionByMonthChart months={MONTHS} />
      </div>,
    );
    const bars = container.querySelectorAll('.recharts-bar-rectangle');
    expect(bars.length).toBeGreaterThan(0);
  });
});
