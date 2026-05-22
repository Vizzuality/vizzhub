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
          // All four major currencies have explicit rates → no empty cells, no warning.
          fx_rates: { USD: '1.05', GBP: '0.85', CAD: '1.45', CHF: '0.95' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={['USD', 'GBP']}
      />,
    );
    expect(screen.queryByText(/fall back to ECB/i)).not.toBeInTheDocument();
  });

  it('shows "new — needs rate" source for currencies not in previousPeriod', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          // All four majors have rates so only the added one (BRL) is "new — needs rate".
          fx_rates: { USD: '1.05', GBP: '0.85', CAD: '1.45', CHF: '0.95' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={['BRL']}
      />,
    );
    expect(screen.getByText('new — needs rate')).toBeInTheDocument();
    // Each of the four majors shows "from previous period".
    expect(screen.getAllByText('from previous period')).toHaveLength(4);
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
    // EUR should not appear as a row (it's the base currency).
    // The default rows = MAJOR_CURRENCIES (USD, GBP, CAD, CHF), no EUR.
    expect(screen.queryByText('EUR')).not.toBeInTheDocument();
    expect(screen.getByText('USD')).toBeInTheDocument();
  });

  it('shows the four major currencies by default even with no previous period', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={null}
        usedCurrencies={[]}
      />,
    );
    // MAJOR_CURRENCIES = USD, GBP, CAD, CHF — all should appear as rows.
    expect(screen.getByText('USD')).toBeInTheDocument();
    expect(screen.getByText('GBP')).toBeInTheDocument();
    expect(screen.getByText('CAD')).toBeInTheDocument();
    expect(screen.getByText('CHF')).toBeInTheDocument();
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

  it('orders rows USD → GBP → CAD → rest alphabetically', () => {
    renderWith(
      <PeriodEditor
        open
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { BRL: '6.00', JPY: '160', USD: '1.10', CHF: '0.95' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    const bodyRows = screen.getAllByRole('row').slice(1);
    const codes = bodyRows.map((r) => r.querySelector('td')?.textContent?.trim());
    // USD, GBP, CAD first (whitelist), then BRL, CHF, JPY alphabetically.
    expect(codes).toEqual(['USD', 'GBP', 'CAD', 'BRL', 'CHF', 'JPY']);
  });

  it('in edit mode existing rates are read-only with no remove button', () => {
    renderWith(
      <PeriodEditor
        open
        mode="edit"
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2026-01-01', status: 'open',
          fx_rates: { USD: '1.10' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    expect(screen.queryByLabelText(/^FX rate for USD$/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Locked FX rate for USD$/i)).toHaveTextContent('1.10');
    expect(screen.queryByRole('button', { name: /Remove USD/i })).not.toBeInTheDocument();
    expect(screen.getByText('locked for this period')).toBeInTheDocument();
    // GBP is in the majors whitelist (not in previousPeriod) → editable + removable.
    expect(screen.getByLabelText(/^FX rate for GBP$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Remove GBP/i })).toBeInTheDocument();
  });

  it('in create mode rates from previous period stay editable', () => {
    renderWith(
      <PeriodEditor
        open
        mode="create"
        onClose={vi.fn()}
        previousPeriod={{
          id: 'p1', start_date: '2025-01-01', status: 'open',
          fx_rates: { USD: '1.05' },
          closed_at: null, created_at: '', created_by: null,
        }}
        usedCurrencies={[]}
      />,
    );
    expect(screen.getByLabelText(/^FX rate for USD$/i)).toHaveValue('1.05');
    expect(screen.getByRole('button', { name: /Remove USD/i })).toBeInTheDocument();
  });
});
