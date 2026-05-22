import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import { Periods } from '@/modules/accrual/pages/Periods';

vi.mock('@/modules/accrual/hooks/usePeriods', () => ({
  usePeriodsList: () => ({
    data: [
      {
        id: 'p1', start_date: '2026-01-01', status: 'open',
        fx_rates: { USD: '1.10' }, closed_at: null, created_at: '2026-01-01T00:00:00Z',
        created_by: null,
      },
      {
        id: 'p0', start_date: '2025-01-01', status: 'closed',
        fx_rates: { USD: '1.05' }, closed_at: '2026-01-01T00:00:00Z',
        created_at: '2025-01-01T00:00:00Z', created_by: null,
      },
    ],
    isLoading: false,
  }),
  useCurrentPeriod: () => ({ data: null }),
  useCreatePeriod: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

const renderPage = (): void => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><Periods /></MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('Periods page', () => {
  it('lists periods, open status visible', () => {
    renderPage();
    expect(screen.getByText('open')).toBeInTheDocument();
    expect(screen.getByText('closed')).toBeInTheDocument();
  });

  it('opens the new-period dialog on button click', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /new period/i }));
    expect(screen.getByText(/Open new accrual period/i)).toBeInTheDocument();
  });
});
