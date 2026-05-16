import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

function makePeriods(count: number): PeriodInsight[] {
  return Array.from({ length: count }, (_, i) => {
    const month = String((i % 12) + 1).padStart(2, '0');
    const year = 2025 + Math.floor(i / 12);
    return {
      period: `${year}-${month}`,
      functional_areas: [
        { short: 'FE', billable_pct: 0.5, absence_pct: 0.1, other_pct: 0.4, user_count: 2 },
      ],
    };
  });
}

describe('InsightsChart', () => {
  it('renders Other segment when other_pct > 0', () => {
    const data: PeriodInsight[] = [
      {
        period: '2026-01',
        functional_areas: [
          { short: 'FE', billable_pct: 0.5, absence_pct: 0.1, other_pct: 0.4, user_count: 2 },
        ],
      },
    ];

    render(<InsightsChart data={data} />);

    expect(screen.getByText('Other')).toBeInTheDocument();
    expect(screen.getByText('Absence')).toBeInTheDocument();
    expect(screen.getByText('FE')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<InsightsChart data={[]} />);
    expect(screen.getByText('No data for the selected period')).toBeInTheDocument();
  });

  it('defaults to the latest 6-month window on mount when data exceeds the page size', () => {
    // 14 months → 3 pages of 6. Pagination should show "3 / 3" on mount,
    // i.e. the most recent window — not "1 / 3" (the audit bug).
    render(<InsightsChart data={makePeriods(14)} />);
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
  });

  it('preserves backward navigation: clicking < moves to an older window', () => {
    render(<InsightsChart data={makePeriods(14)} />);
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
    // Two buttons in the pagination row: previous (<) and next (>).
    const prev = screen.getAllByRole('button')[0];
    fireEvent.click(prev);
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
  });

  it('stays on page 1 when data fits in a single window', () => {
    render(<InsightsChart data={makePeriods(6)} />);
    // Pagination is hidden when totalPages <= 1.
    expect(screen.queryByText(/\/ 1$/)).not.toBeInTheDocument();
  });
});
