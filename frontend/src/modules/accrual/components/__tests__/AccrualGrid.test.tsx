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
  data_quality_note: null,
  dates_diverged: false,
  rate: null,
  period_rate: null,
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
    // 6 sticky cols + 2 months = 8
    expect(headers.length).toBeGreaterThanOrEqual(8);
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

  it('links the line name to its tracker project when it maps to a single project', () => {
    renderGrid();
    const nameLink = screen.getByRole('link', { name: 'Project A' });
    expect(nameLink).toHaveAttribute('href', '/tracker/projects/p1');
  });

  it('renders the line name as plain text (no link) for a multi-project line', () => {
    const multi: AccrualGridLine = {
      ...line,
      projects: [
        { ...line.projects[0] },
        { ...line.projects[0], id: 'p2', code: 'A.2', name: 'Project A2' },
      ],
    };
    renderGrid({ lines: [multi] });
    expect(screen.queryByRole('link', { name: 'Project A' })).toBeNull();
    expect(screen.getByText('Project A')).toBeInTheDocument();
  });

  it('renders an edit button next to the code when onEditLine is provided', async () => {
    const onEditLine = vi.fn();
    renderGrid({ onEditLine });
    const editBtn = screen.getByRole('button', { name: /edit project a/i });
    await userEvent.click(editBtn);
    expect(onEditLine).toHaveBeenCalledWith('line1');
  });

  it('does not render the edit button when onEditLine is absent (no manage permission)', () => {
    renderGrid({ onEditLine: undefined });
    expect(screen.queryByRole('button', { name: /edit project a/i })).toBeNull();
  });

  it('renders the amount for months with a cell and zero for months without', () => {
    renderGrid();
    // Jan has 100.00, Feb has none → at least one "0.00" in the document
    expect(screen.getByText('100.00')).toBeInTheDocument();
    expect(screen.getAllByText('0.00').length).toBeGreaterThanOrEqual(1);
  });

  it('totals row sums EUR amounts per column', () => {
    renderGrid();
    // Jan column total = 90.91 (only cell), formatted as 90.91. The totals row is
    // pinned above the column headers; locate it by its label, not position.
    const totalsRow = screen.getByText('Totals (EUR)').closest('tr');
    expect(totalsRow).not.toBeNull();
    expect(within(totalsRow as HTMLElement).getByText('90.91')).toBeInTheDocument();
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

  it('renders a data-quality warning with the note as tooltip when set', () => {
    const note = 'Original amount unreliable: the source recorded a wrong currency or rate.';
    renderGrid({ lines: [{ ...line, data_quality_note: note }] });
    const icon = screen.getByTestId('data-quality-warning');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute('aria-label', note);
  });

  it('shows a divergence warning when project dates differ from the window', () => {
    renderGrid({ lines: [{ ...line, id: 'l-div', dates_diverged: true }] });
    const warnings = screen.getAllByTestId('data-quality-warning');
    expect(
      warnings.some((w) => (w.getAttribute('aria-label') ?? '').includes('Project dates differ')),
    ).toBe(true);
  });

  it('renders no data-quality warning when the note is null', () => {
    renderGrid();
    expect(screen.queryByTestId('data-quality-warning')).toBeNull();
  });

  it('shows the per-line CEO rate in the Rate column (override, coloured) when present', () => {
    renderGrid({ lines: [{ ...line, value_orig: '1200.00', currency: 'USD', rate: '1.08', period_rate: null }] });
    // Rate column renders override formatted to 4dp; the @fragment no longer lives in Original
    expect(screen.getByText('1.0800')).toBeInTheDocument();
  });

  it('renders an em-dash for the Original column when the line has no foreign value', () => {
    renderGrid({ lines: [{ ...line, value_orig: null, currency: null, rate: null }] });
    // The line keeps its excel_code, so the only em-dash is the empty Original cell.
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('badges non-excel provenance but not excel lines', () => {
    renderGrid({ lines: [{ ...line, source: 'team_budget' }] });
    expect(screen.getByText('Team budget')).toBeInTheDocument();
  });

  it('hides a static column when its id is absent from visibleStaticIds', () => {
    // Drop the Projects column → its project link should disappear.
    renderGrid({ visibleStaticIds: ['code', 'name', 'original', 'value_eur'] });
    expect(screen.queryByRole('link', { name: 'A.1' })).toBeNull();
  });

  it('calls onSort with the column key when a sortable header is clicked', async () => {
    const onSort = vi.fn();
    renderGrid({ onSort, sort: null });
    await userEvent.click(screen.getByRole('button', { name: /sort by line/i }));
    expect(onSort).toHaveBeenCalledWith('name');
  });

  it('marks the active sort header with its direction indicator', () => {
    renderGrid({ sort: { key: 'value_eur', dir: 'desc' }, onSort: vi.fn() });
    const header = screen.getByRole('button', { name: /sort by value/i });
    expect(header).toHaveClass('text-foreground');
  });
});
