import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import ProgressCard from '../ProgressCard';
import NonStaffCostsCard from '../NonStaffCostsCard';

// Periods with no reported cost must still be pickable: the cards read the full
// reporting-period list, not the cost summary (which only has months with cost).
const PERIODS = [
  { id: 'p-nov', date: '2026-11-01', base_rate: 175, status: 'active', report_count: 0 },
  { id: 'p-jul', date: '2026-07-01', base_rate: 175, status: 'finished', report_count: 4 },
];

vi.mock('../../hooks/useReportingPeriods', () => ({
  useReportingPeriods: () => ({ data: PERIODS }),
}));

const mutation = { mutate: vi.fn(), isPending: false };

vi.mock('../../hooks/useProgress', () => ({
  useProjectProgress: () => ({
    data: [
      {
        id: 'pr-1',
        project_id: 'proj-1',
        reporting_period_id: 'p-jul',
        period_date: '2026-07-01',
        percentage: 95,
        delta: 95,
      },
    ],
  }),
  useCreateProgress: () => mutation,
  useUpdateProgress: () => mutation,
  useDeleteProgress: () => mutation,
}));

vi.mock('../../hooks/useNonStaffCosts', () => ({
  useNonStaffCosts: () => ({ data: [] }),
  useCreateNonStaffCost: () => mutation,
  useUpdateNonStaffCost: () => mutation,
  useDeleteNonStaffCost: () => mutation,
}));

function periodOptions(): string[] {
  const select = screen.getAllByRole('combobox')[0];
  return within(select)
    .getAllByRole('option')
    .map((o) => o.textContent ?? '');
}

describe('period pickers', () => {
  it('ProgressCard offers periods without cost and hides those with progress', () => {
    render(<ProgressCard projectId="proj-1" />);
    fireEvent.click(screen.getByRole('button', { name: /add progress/i }));

    const options = periodOptions();
    expect(options.some((o) => o.includes('November 2026'))).toBe(true);
    expect(options.some((o) => o.includes('July 2026'))).toBe(false);
  });

  it('NonStaffCostsCard offers every reporting period', () => {
    render(<NonStaffCostsCard projectId="proj-1" />);
    fireEvent.click(screen.getByRole('button', { name: /add cost/i }));

    const options = periodOptions();
    expect(options.some((o) => o.includes('November 2026'))).toBe(true);
    expect(options.some((o) => o.includes('July 2026'))).toBe(true);
  });
});
