import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { server } from '@/test/setup';
import { useAccrualDashboard } from '../useAccrualDashboard';

function makeWrapper(): ({ children }: { children: ReactNode }) => JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }): JSX.Element {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('useAccrualDashboard', () => {
  it('fetches the summary for the given year', async () => {
    server.use(
      http.get('/api/accrual/dashboard/summary', ({ request }) => {
        const year = Number(new URL(request.url).searchParams.get('year'));
        return HttpResponse.json({
          year,
          available_years: [2025, 2026],
          months: [{ month: 1, amount_eur: 100, status: 'recognized', prev_amount_eur: 80 }],
          kpis: {
            recognized_ytd_eur: 100,
            recognized_quarter_eur: 100,
            contracted_total_eur: 1000,
            backlog_eur: 900,
            plan_recognized_pct: 10,
            recognized_prev_ytd_eur: 80,
            yoy_pct: 25,
          },
        });
      }),
    );
    const { result } = renderHook(() => useAccrualDashboard(2026), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.data?.year).toBe(2026));
    expect(result.current.data?.months).toHaveLength(1);
  });
});
