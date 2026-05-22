import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import {
  usePeriodsList,
  useCurrentPeriod,
  useCreatePeriod,
  usePatchPeriod,
} from '@/modules/accrual/hooks/usePeriods';
import { accrualApi } from '@/modules/accrual/services/accrual';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    periods: { list: vi.fn(), current: vi.fn(), create: vi.fn(), patch: vi.fn() },
  },
}));

const wrap = (qc: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };

beforeEach(() => vi.clearAllMocks());

describe('usePeriodsList', () => {
  it('calls list and exposes data', async () => {
    (accrualApi.periods.list as any).mockResolvedValue([
      { id: 'p1', start_date: '2026-01-01', status: 'open', fx_rates: {} },
    ]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePeriodsList(), { wrapper: wrap(qc) });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.[0].id).toBe('p1');
  });
});

describe('useCurrentPeriod', () => {
  it('calls current and exposes data', async () => {
    (accrualApi.periods.current as any).mockResolvedValue({ id: 'p1', status: 'open' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCurrentPeriod(), { wrapper: wrap(qc) });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.id).toBe('p1');
  });
});

describe('useCreatePeriod', () => {
  it('invalidates periods queries on success', async () => {
    (accrualApi.periods.create as any).mockResolvedValue({ id: 'p2' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useCreatePeriod(), { wrapper: wrap(qc) });
    await result.current.mutateAsync({ start_date: '2026-01-01', fx_rates: { USD: '1.10' } });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['accrual', 'periods'] });
  });
});

describe('usePatchPeriod', () => {
  it('invalidates periods queries on success', async () => {
    (accrualApi.periods.patch as any).mockResolvedValue({ id: 'p1' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => usePatchPeriod(), { wrapper: wrap(qc) });
    await result.current.mutateAsync({ id: 'p1', payload: { fx_rates: { USD: '1.11' } } });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['accrual', 'periods'] });
  });
});
