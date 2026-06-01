import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '@/test/setup';
import { AccrualDashboard } from '../Dashboard';

function renderPage(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/admin/accrual/dashboard']}>
        <AccrualDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AccrualDashboard', () => {
  it('renders KPI cards from the summary', async () => {
    server.use(
      http.get('/api/accrual/dashboard/summary', () =>
        HttpResponse.json({
          year: 2026,
          available_years: [2025, 2026],
          months: Array.from({ length: 12 }, (_, i) => ({
            month: i + 1,
            amount_eur: 100,
            status: 'recognized',
          })),
          kpis: {
            recognized_ytd_eur: 1200,
            recognized_quarter_eur: 300,
            contracted_total_eur: 5000,
            backlog_eur: 3800,
            manual_pct: 0,
          },
        }),
      ),
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/Recognized YTD/i)).toBeInTheDocument());
  });

  it('changing the year via the navigator updates the year display', async () => {
    // Default handler bounds are [2025, 2026]; current year (2026) is the max,
    // so "next year" is disabled. Navigate to the previous (enabled) year instead.
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /previous year/i })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole('button', { name: /previous year/i }));
    await waitFor(() =>
      expect(screen.getByTestId('accrual-dashboard-year')).toHaveTextContent('2025'),
    );
  });
});
