import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AccrualGrid } from '@/modules/accrual/components/AccrualGrid';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridMonth,
  AccrualGridProject,
} from '@/modules/accrual/types/accrual';

const project: AccrualGridProject = {
  id: 'p1',
  code: 'A.1',
  name: 'Project A',
  currency: 'USD',
  budget: '1200.00',
  original_budget: '1200.00',
  budget_eur: '1090.91',
  locked_fx_rate: null,
  status: 'live',
  start_date: '2026-01-01',
  end_date: '2026-12-01',
  project_manager_id: null,
  project_manager_name: null,
};

const months: AccrualGridMonth[] = [
  { year: 2026, month: 1 },
  { year: 2026, month: 2 },
];

const cellJan: AccrualCellType = {
  id: 'c-jan',
  project_id: 'p1',
  year: 2026,
  month: 1,
  amount: '100.00',
  eur_amount: '90.91',
  is_manual_override: false,
  is_frozen: false,
  frozen_at: null,
  frozen_rate: null,
  frozen_eur_amount: null,
  updated_at: '2026-05-01T00:00:00Z',
};

function renderGrid(
  overrides: Partial<React.ComponentProps<typeof AccrualGrid>> = {},
): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AccrualGrid
          projects={[project]}
          cells={[cellJan]}
          months={months}
          onCellChange={vi.fn()}
          canEdit
          {...overrides}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AccrualGrid', () => {
  it('renders one row per project + a totals row', () => {
    renderGrid();
    // thead has 2 rows (year group + column headers); tbody has 1 project; tfoot has 1 totals row
    const rows = screen.getAllByRole('row');
    // 2 header rows + 1 data row + 1 totals row = 4
    expect(rows).toHaveLength(4);
  });

  it('renders one column header per month plus the sticky-left columns', () => {
    renderGrid();
    const headers = screen.getAllByRole('columnheader');
    // 7 sticky cols + 2 months = 9
    expect(headers.length).toBeGreaterThanOrEqual(9);
  });

  it('shows the project name as a link to the project detail page', () => {
    renderGrid();
    const link = screen.getByRole('link', { name: /project a/i });
    expect(link).toHaveAttribute('href', '/tracker/projects/p1');
  });

  it('renders the amount for months with a cell and zero for months without', () => {
    renderGrid();
    // Jan has 100.00, Feb has none → at least one "0.00" in the document
    expect(screen.getByText('100.00')).toBeInTheDocument();
    expect(screen.getAllByText('0.00').length).toBeGreaterThanOrEqual(1);
  });

  it('totals row sums EUR amounts per column', () => {
    renderGrid();
    // Jan column total = 90.91 (only cell), formatted as 90.91
    const rows = screen.getAllByRole('row');
    const totalsRow = rows[rows.length - 1];
    expect(within(totalsRow).getByText('90.91')).toBeInTheDocument();
  });

  it('triggers onCellChange when an editable cell is committed', async () => {
    const onCellChange = vi.fn();
    renderGrid({ onCellChange });
    // Find the Jan cell button and edit it
    const jan = screen.getByText('100.00').closest('button');
    expect(jan).not.toBeNull();
    await userEvent.click(jan!);
    const input = screen.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, '250');
    await userEvent.keyboard('{Enter}');
    expect(onCellChange).toHaveBeenCalledWith('p1', 2026, 1, '250');
  });

  it('shows the destructive ring on cells in failedCells', () => {
    renderGrid({ failedCells: new Set(['p1:2026:1']) });
    // The jan cell should have the error styling.
    const jan = screen.getByText('100.00').closest('button');
    expect(jan?.className).toContain('ring-destructive');
  });
});
