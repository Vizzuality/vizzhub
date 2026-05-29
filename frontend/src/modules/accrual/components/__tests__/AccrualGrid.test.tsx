import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AccrualGrid } from '@/modules/accrual/components/AccrualGrid';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridLine,
  AccrualGridMonth,
} from '@/modules/accrual/types/accrual';

const line: AccrualGridLine = {
  id: 'line1',
  name: 'Project A',
  source: 'excel',
  excel_code: 'A.1',
  value_eur: '1090.91',
  value_orig: '1200.00',
  currency: 'USD',
  window_start: '2026-01-01',
  window_end: '2026-12-01',
  projects: [
    {
      id: 'p1',
      code: 'A.1',
      name: 'Project A',
      status: 'live',
      project_manager_id: null,
      project_manager_name: null,
    },
  ],
  health: { status: 'ok', diff_eur: '0.00', diff_pct: 0 },
};

const months: AccrualGridMonth[] = [
  { year: 2026, month: 1 },
  { year: 2026, month: 2 },
];

const cellJan: AccrualCellType = {
  id: 'c-jan',
  line_id: 'line1',
  project_id: 'p1',
  year: 2026,
  month: 1,
  amount: '100.00',
  eur_amount: '90.91',
  is_manual_override: false,
  is_frozen: false,
  frozen_at: null,
  frozen_eur_amount: null,
  source: 'excel',
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
          lines={[line]}
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
  it('renders one row per line + a totals row', () => {
    renderGrid();
    // thead has 2 rows (year group + column headers); tbody has 1 line; tfoot has 1 totals row
    const rows = screen.getAllByRole('row');
    // 2 header rows + 1 data row + 1 totals row = 4
    expect(rows).toHaveLength(4);
  });

  it('renders one column header per month plus the sticky-left columns', () => {
    renderGrid();
    const headers = screen.getAllByRole('columnheader');
    // 5 sticky cols + 2 months = 7
    expect(headers.length).toBeGreaterThanOrEqual(7);
  });

  it('shows each linked project as a link to its detail page', () => {
    renderGrid();
    const link = screen.getByRole('link', { name: 'A.1' });
    expect(link).toHaveAttribute('href', '/tracker/projects/p1');
  });

  it('renders "no project" for an unlinked line', () => {
    renderGrid({ lines: [{ ...line, projects: [] }] });
    expect(screen.getByText(/no project/i)).toBeInTheDocument();
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

  it('triggers onCellChange (keyed by line id) when an editable cell is committed', async () => {
    const onCellChange = vi.fn();
    renderGrid({ onCellChange });
    const jan = screen.getByText('100.00').closest('button');
    expect(jan).not.toBeNull();
    await userEvent.click(jan!);
    const input = screen.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, '250');
    await userEvent.keyboard('{Enter}');
    expect(onCellChange).toHaveBeenCalledWith('line1', 2026, 1, '250');
  });

  it('shows the destructive ring on cells in failedCells (keyed by line id)', () => {
    renderGrid({ failedCells: new Set(['line1:2026:1']) });
    const jan = screen.getByText('100.00').closest('button');
    expect(jan?.className).toContain('ring-destructive');
  });

  it('does not render a health indicator when status is ok', () => {
    renderGrid();
    expect(screen.queryByTestId('health-warning')).toBeNull();
    expect(screen.queryByTestId('health-critical')).toBeNull();
  });

  it('renders a warning icon next to the line name when health is warning', () => {
    const warnLine: AccrualGridLine = {
      ...line,
      health: { status: 'warning', diff_eur: '120.00', diff_pct: 10 },
    };
    renderGrid({ lines: [warnLine] });
    expect(screen.getByTestId('health-warning')).toBeInTheDocument();
  });

  it('renders a critical icon for a heavily diverging line', () => {
    const critLine: AccrualGridLine = {
      ...line,
      health: { status: 'critical', diff_eur: '-1090.91', diff_pct: 100 },
    };
    renderGrid({ lines: [critLine] });
    expect(screen.getByTestId('health-critical')).toBeInTheDocument();
  });

  it('shows a positive diff badge next to Value € when cells exceed the line value', () => {
    const warnLine: AccrualGridLine = {
      ...line,
      health: { status: 'warning', diff_eur: '120.00', diff_pct: 11 },
    };
    renderGrid({ lines: [warnLine] });
    expect(screen.getByText('+11%')).toBeInTheDocument();
  });

  it('shows a negative diff badge when cells are under the line value', () => {
    const underLine: AccrualGridLine = {
      ...line,
      health: { status: 'critical', diff_eur: '-1090.91', diff_pct: 100 },
    };
    renderGrid({ lines: [underLine] });
    expect(screen.getByText('−100%')).toBeInTheDocument();
  });

  it('badges non-excel provenance but not excel lines', () => {
    renderGrid({ lines: [{ ...line, source: 'team_budget' }] });
    expect(screen.getByText('Team budget')).toBeInTheDocument();
  });
});
