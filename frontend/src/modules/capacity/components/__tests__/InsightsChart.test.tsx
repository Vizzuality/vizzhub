import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

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
});
