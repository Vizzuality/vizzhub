import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useAccrualGrid } from '@/modules/accrual/hooks/useAccrualGrid';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type { AccrualGridResponse } from '@/modules/accrual/types/accrual';

vi.mock('@/modules/accrual/services/accrual', () => ({
  accrualApi: {
    cells: { grid: vi.fn() },
  },
}));

const wrap = (qc: QueryClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };

beforeEach(() => vi.clearAllMocks());

const mockGrid: AccrualGridResponse = {
  projects: [
    {
      id: 'proj-1',
      name: 'Project Alpha',
      currency: 'USD',
      status: 'live',
      project_manager_id: null,
      project_manager_name: null,
    },
  ],
  cells: [
    {
      id: 'cell-1',
      project_id: 'proj-1',
      year: 2026,
      month: 1,
      amount: '1000.00',
      is_manual_override: false,
      is_frozen: false,
      frozen_at: null,
      frozen_eur_amount: null,
      eur_amount: null,
      source: 'excel',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  months: [{ year: 2026, month: 1 }],
};

describe('useAccrualGrid', () => {
  it('returns grid data on success', async () => {
    (accrualApi.cells.grid as any).mockResolvedValue(mockGrid);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useAccrualGrid({ year_from: 2026, year_to: 2026 }),
      { wrapper: wrap(qc) },
    );
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.projects).toHaveLength(1);
    expect(result.current.data?.cells).toHaveLength(1);
    expect(result.current.data?.months).toHaveLength(1);
  });

  it('passes filters through to the service', async () => {
    (accrualApi.cells.grid as any).mockResolvedValue(mockGrid);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const filters = { year_from: 2025, year_to: 2026, status: 'live', currency: 'USD' };
    const { result } = renderHook(() => useAccrualGrid(filters), { wrapper: wrap(qc) });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(accrualApi.cells.grid).toHaveBeenCalledWith(filters);
  });

  it('exposes isLoading before data resolves', () => {
    (accrualApi.cells.grid as any).mockImplementation(
      () => new Promise(() => {/* pending */}),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useAccrualGrid({ year_from: 2026, year_to: 2026 }),
      { wrapper: wrap(qc) },
    );
    expect(result.current.isLoading).toBe(true);
  });
});
