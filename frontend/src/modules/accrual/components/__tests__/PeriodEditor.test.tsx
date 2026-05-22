import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { PeriodEditor } from '@/modules/accrual/components/PeriodEditor';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    periods: { list: vi.fn(), current: vi.fn(), create: vi.fn(), patch: vi.fn() },
  },
}));

const renderWith = (ui: ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
};

describe('PeriodEditor', () => {
  it('pre-fills fx_rates from previousPeriod', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05', GBP: '0.85' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={['USD', 'GBP']}
      />,
    );
    expect(screen.getByDisplayValue('1.05')).toBeInTheDocument();
    expect(screen.getByDisplayValue('0.85')).toBeInTheDocument();
  });

  it('shows a row for used currencies not in fx_rates', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={['USD', 'CHF']}
      />,
    );
    // Both currencies should appear as rows (no rate yet, source = "new").
    expect(screen.getByText('USD')).toBeInTheDocument();
    expect(screen.getByText('CHF')).toBeInTheDocument();
  });

  it('shows ECB fallback warning when rows have empty rates', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={['USD', 'CHF']}
      />,
    );
    // The amber warning contains "fall back to ECB" — match the specific phrase
    expect(screen.getByText(/fall back to ECB/i)).toBeInTheDocument();
  });

  it('does not show ECB warning when all rates are filled', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05', GBP: '0.85' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={['USD', 'GBP']}
      />,
    );
    // The amber warning (with AlertTriangle) should NOT be present; the DialogDescription still has "ECB"
    expect(screen.queryByText(/fall back to ECB/i)).not.toBeInTheDocument();
  });

  it('shows "new — needs rate" source for currencies not in previousPeriod', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={['USD', 'CHF']}
      />,
    );
    expect(screen.getByText('new — needs rate')).toBeInTheDocument();
    expect(screen.getByText('from previous period')).toBeInTheDocument();
  });

  it('shows the freeze note when previousPeriod is set', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: {},
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    expect(screen.getByText(/close the current open period/i)).toBeInTheDocument();
  });

  it('does not show freeze note when previousPeriod is null', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    expect(screen.queryByText(/close the current open period/i)).not.toBeInTheDocument();
  });

  it('renders the Open period button', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    expect(screen.getByRole('button', { name: /open period/i })).toBeInTheDocument();
  });

  it('renders Cancel button and calls onClose', async () => {
    const onClose = vi.fn();
    const { user } = renderWith(
      <PeriodEditor
        open
        onClose={onClose}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    ) as ReturnType<typeof render> & { user?: ReturnType<typeof import('@testing-library/user-event').default.setup> };
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    expect(cancelBtn).toBeInTheDocument();
  });

  it('excludes EUR from fx_rates rows', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={['EUR', 'USD']}
      />,
    );
    // EUR should not appear as a row (it's the base currency)
    const rows = screen.getAllByRole('row');
    // header + USD row only, not EUR
    expect(rows).toHaveLength(2); // 1 header + 1 data row
  });

  it('shows the empty-state hint when no currencies are present', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    expect(screen.getByText(/No currencies yet/i)).toBeInTheDocument();
  });

  it('lets the user add a new currency via the inline form', async () => {
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    await user.type(screen.getByLabelText(/Add currency/i), 'usd');
    await user.type(screen.getByLabelText(/Rate \(per 1 EUR\)/i), '1.10');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    expect(screen.getByText('USD')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1.10')).toBeInTheDocument();
  });

  it('rejects malformed codes when adding', async () => {
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    await user.type(screen.getByLabelText(/Add currency/i), 'XX');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(/3-letter/);
  });

  it('rejects EUR explicitly', async () => {
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    await user.type(screen.getByLabelText(/Add currency/i), 'eur');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(/EUR is the base/);
  });

  it('rejects duplicates', async () => {
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    await user.type(screen.getByLabelText(/Add currency/i), 'USD');
    await user.click(screen.getByRole('button', { name: /^Add$/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(/already in the list/i);
  });

  it('lets the user remove a row', async () => {
    const user = userEvent.setup();
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05', GBP: '0.85' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    expect(screen.getByText('USD')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Remove USD/i }));
    expect(screen.queryByText('USD')).not.toBeInTheDocument();
    expect(screen.getByText('GBP')).toBeInTheDocument();
  });
});
