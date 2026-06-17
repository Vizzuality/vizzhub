import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useLineMutations } from '@/modules/accrual/hooks/useLineMutations';
import { accrualApi } from '@/modules/accrual/services/accrual';
import { queryKeys } from '@/core/hooks/queryKeys';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    lines: {
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
      linkProject: vi.fn(),
      unlinkProject: vi.fn(),
    },
  },
}));

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => vi.clearAllMocks());

describe('useLineMutations', () => {
  it('create calls lines.create with the payload', async () => {
    vi.mocked(accrualApi.lines.create).mockResolvedValue({ id: 'l1' } as never);
    const { result } = renderHook(() => useLineMutations(), { wrapper });
    await act(async () => {
      await result.current.create.mutateAsync({ name: 'X', value_eur: '100' });
    });
    expect(accrualApi.lines.create).toHaveBeenCalledWith({ name: 'X', value_eur: '100' });
  });

  it('update calls lines.update with id + payload', async () => {
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l1' } as never);
    const { result } = renderHook(() => useLineMutations(), { wrapper });
    await act(async () => {
      await result.current.update.mutateAsync({ id: 'l1', payload: { value_eur: '200' } });
    });
    expect(accrualApi.lines.update).toHaveBeenCalledWith('l1', { value_eur: '200' });
  });

  it('remove calls lines.remove with the id', async () => {
    vi.mocked(accrualApi.lines.remove).mockResolvedValue(undefined as never);
    const { result } = renderHook(() => useLineMutations(), { wrapper });
    await act(async () => {
      await result.current.remove.mutateAsync('l1');
    });
    expect(accrualApi.lines.remove).toHaveBeenCalledWith('l1');
  });

  it('update invalidates the dashboard so totals reflect moved cells', async () => {
    vi.mocked(accrualApi.lines.update).mockResolvedValue({ id: 'l1' } as never);
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const localWrapper = ({ children }: { children: ReactNode }): JSX.Element => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useLineMutations(), { wrapper: localWrapper });
    await act(async () => {
      await result.current.update.mutateAsync({ id: 'l1', payload: { window_start: '2024-01-01' } });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.accrual.dashboard.all });
  });

  it('linkProject / unlinkProject call the right endpoints', async () => {
    vi.mocked(accrualApi.lines.linkProject).mockResolvedValue({ id: 'l1' } as never);
    vi.mocked(accrualApi.lines.unlinkProject).mockResolvedValue({ id: 'l1' } as never);
    const { result } = renderHook(() => useLineMutations(), { wrapper });
    await act(async () => {
      await result.current.linkProject.mutateAsync({ id: 'l1', projectId: 'p1' });
      await result.current.unlinkProject.mutateAsync({ id: 'l1', projectId: 'p1' });
    });
    expect(accrualApi.lines.linkProject).toHaveBeenCalledWith('l1', 'p1');
    expect(accrualApi.lines.unlinkProject).toHaveBeenCalledWith('l1', 'p1');
  });
});
