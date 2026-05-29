import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import {
  usePeriodsList,
  useCurrentPeriod,
  useCreatePeriod,
} from '@/modules/accrual/hooks/usePeriods';
import { accrualApi } from '@/modules/accrual/services/accrual';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    periods: { list: vi.fn(), current: vi.fn(), create: vi.fn() },
  },
}));

const wrap = (qc: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };

beforeEach(() => vi.clearAllMocks());

describe('usePeriodsList', () => {
  it('calls list and exposes data', async () => {
    vi.mocked(accrualApi.periods.list).mockResolvedValue([
      { id: 'p1', start_date: '2026-01-01', status: 'open' },
    ]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePeriodsList(), { wrapper: wrap(qc) });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.[0].id).toBe('p1');
  });
});

describe('useCurrentPeriod', () => {
  it('calls current and exposes data', async () => {
    vi.mocked(accrualApi.periods.current).mockResolvedValue({ id: 'p1', status: 'open' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCurrentPeriod(), { wrapper: wrap(qc) });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.id).toBe('p1');
  });
});

describe('useCreatePeriod', () => {
  it('invalidates periods queries on success', async () => {
    vi.mocked(accrualApi.periods.create).mockResolvedValue({ id: 'p2' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useCreatePeriod(), { wrapper: wrap(qc) });
    await result.current.mutateAsync({ start_date: '2026-01-01' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['accrual', 'periods'] });
  });
});
