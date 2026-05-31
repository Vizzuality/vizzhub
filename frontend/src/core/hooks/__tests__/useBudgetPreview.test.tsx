import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { server } from '@/test/setup';
import { useBudgetPreview } from '../useBudgetPreview';

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useBudgetPreview', () => {
  it('returns the derived EUR when inputs are valid', async () => {
    server.use(
      http.get('/api/projects/budget-preview', () => HttpResponse.json({ budget_eur: 800 })),
    );
    const { result } = renderHook(
      () => useBudgetPreview({ originalBudget: '1000', currency: 'dollar', startDate: '2026-01-01' }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.data?.budget_eur).toBe(800));
  });

  it('is disabled (no fetch) when amount is missing', () => {
    const { result } = renderHook(
      () => useBudgetPreview({ originalBudget: '', currency: 'dollar', startDate: '2026-01-01' }),
      { wrapper },
    );
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('re-fetches with the new value when inputs change', async () => {
    const seen: string[] = [];
    server.use(
      http.get('/api/projects/budget-preview', ({ request }) => {
        const amount = new URL(request.url).searchParams.get('original_budget');
        seen.push(amount ?? '');
        return HttpResponse.json({ budget_eur: Number(amount) / 2 });
      }),
    );
    const { result, rerender } = renderHook(
      ({ amount }: { amount: string }) =>
        useBudgetPreview({ originalBudget: amount, currency: 'dollar', startDate: '2026-01-01' }),
      { wrapper, initialProps: { amount: '1000' } },
    );
    await waitFor(() => expect(result.current.data?.budget_eur).toBe(500));

    rerender({ amount: '2000' });
    await waitFor(() => expect(result.current.data?.budget_eur).toBe(1000));
    expect(seen).toContain('1000');
    expect(seen).toContain('2000');
  });
});
