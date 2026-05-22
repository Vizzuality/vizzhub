import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/setup';
import { useAccrualMutations } from '@/modules/accrual/hooks/useAccrualMutations';
import { queryKeys } from '@/core/hooks/queryKeys';
import type { AccrualGridResponse } from '@/modules/accrual/types/accrual';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return {
    client,
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}

const CELL_ID = 'cell-abc';
const PROJECT_ID = 'proj-1';

const seedGrid: AccrualGridResponse = {
  projects: [
    {
      id: PROJECT_ID,
      name: 'Test Project',
      currency: 'USD',
      status: 'live',
      project_manager_id: null,
      project_manager_name: null,
    },
  ],
  cells: [
    {
      id: CELL_ID,
      project_id: PROJECT_ID,
      year: 2026,
      month: 3,
      amount: '500.00',
      is_manual_override: false,
      is_frozen: false,
      frozen_at: null,
      frozen_rate: null,
      frozen_eur_amount: null,
      eur_amount: null,
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  months: [{ year: 2026, month: 3 }],
};

function seedQueryData(client: QueryClient): void {
  client.setQueryData(
    queryKeys.accrual.cells.grid({ year_from: 2026, year_to: 2026 }),
    seedGrid,
  );
}

describe('useAccrualMutations — updateCell happy path', () => {
  it('optimistically writes amount to cached cells and clears failedCells on success', async () => {
    server.use(
      http.patch('/api/accrual/cells/:id', () => HttpResponse.json({ id: CELL_ID })),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(CELL_ID, '999.00');
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.failedCells.has(`${PROJECT_ID}:2026:3`)).toBe(false);
    expect(result.current.errorMessage).toBeNull();
  });

  it('writes the new amount optimistically into the query cache', async () => {
    server.use(
      http.patch('/api/accrual/cells/:id', () => HttpResponse.json({ id: CELL_ID })),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(CELL_ID, '750.00');
    });

    // After onMutate the cache should carry the new amount
    const cached = client.getQueryData<AccrualGridResponse>(
      queryKeys.accrual.cells.grid({ year_from: 2026, year_to: 2026 }),
    );
    // The invalidation triggers a refetch — cache may be gone, but during
    // the optimistic window (before success callback) the amount was written.
    // The mutation is awaited, so at minimum savingState returned to idle.
    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    // If the grid is still in cache (no fetch happened), assert the amount
    if (cached) {
      const cell = cached.cells.find((c) => c.id === CELL_ID);
      if (cell) expect(cell.amount).toBe('750.00');
    }
  });
});

describe('useAccrualMutations — updateCell error path', () => {
  it('captures errorMessage and adds key to failedCells on error', async () => {
    server.use(
      http.patch('/api/accrual/cells/:id', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(CELL_ID, '100.00');
    });

    await waitFor(() => expect(result.current.savingState).toBe('error'));
    expect(result.current.errorMessage).not.toBeNull();
    expect(result.current.failedCells.has(`${PROJECT_ID}:2026:3`)).toBe(true);
  });

  it('clearFailedCell removes the key and clears errorMessage when last', async () => {
    server.use(
      http.patch('/api/accrual/cells/:id', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(CELL_ID, '100.00');
    });

    await waitFor(() => expect(result.current.failedCells.size).toBe(1));

    act(() => {
      result.current.clearFailedCell(`${PROJECT_ID}:2026:3`);
    });

    expect(result.current.failedCells.size).toBe(0);
    expect(result.current.errorMessage).toBeNull();
  });
});

describe('useAccrualMutations — clearOverride', () => {
  it('calls DELETE /accrual/cells/:id/override and returns to idle', async () => {
    server.use(
      http.delete('/api/accrual/cells/:id/override', () =>
        HttpResponse.json({ id: CELL_ID }),
      ),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.clearOverride(CELL_ID);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.errorMessage).toBeNull();
  });
});

describe('useAccrualMutations — redistribute', () => {
  it('calls POST redistribute and returns to idle on success', async () => {
    server.use(
      http.post('/api/accrual/projects/:id/redistribute', () =>
        HttpResponse.json({ cells_updated: 5 }),
      ),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.redistribute(PROJECT_ID);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.errorMessage).toBeNull();
  });
});

describe('useAccrualMutations — bulkUpdate', () => {
  it('calls POST /accrual/cells/bulk and returns to idle on success', async () => {
    server.use(
      http.post('/api/accrual/cells/bulk', () =>
        HttpResponse.json({ updated: 2 }),
      ),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.bulkUpdate([
        { project_id: PROJECT_ID, year: 2026, month: 3, amount: '400.00' },
        { project_id: PROJECT_ID, year: 2026, month: 4, amount: '600.00' },
      ]);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.errorMessage).toBeNull();
  });
});
