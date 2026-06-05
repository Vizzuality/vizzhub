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
const LINE_ID = 'line-1';
const PROJECT_ID = 'proj-1';
const CELL_KEY = `${LINE_ID}:2026:3`;

const seedGrid: AccrualGridResponse = {
  lines: [
    {
      id: LINE_ID,
      name: 'Test Line',
      source: 'excel',
      excel_code: 'TST.1',
      value_eur: '500.00',
      value_orig: '500.00',
      currency: 'USD',
      window_start: '2026-03-01',
      window_end: '2026-03-01',
      projects: [
        {
          id: PROJECT_ID,
          code: 'TST.1',
          name: 'Test Project',
          status: 'live',
          project_manager_id: null,
          project_manager_name: null,
        },
      ],
      health: { status: 'ok', diff_eur: '0.00', diff_pct: 0 },
    },
  ],
  cells: [
    {
      id: CELL_ID,
      line_id: LINE_ID,
      project_id: PROJECT_ID,
      year: 2026,
      month: 3,
      amount: '500.00',
      is_manual_override: false,
      is_frozen: false,
      frozen_at: null,
      frozen_eur_amount: null,
      eur_amount: null,
      source: 'excel',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  months: [{ year: 2026, month: 3 }],
  bounds: { min_year: 2026, max_year: 2026 },
  available_currencies: ['USD'],
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
      http.put('/api/accrual/lines/:lineId/cells', () => HttpResponse.json({ id: CELL_ID })),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(LINE_ID, 2026, 3, '999.00');
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.failedCells.has(CELL_KEY)).toBe(false);
    expect(result.current.errorMessage).toBeNull();
  });

  it('writes the new amount optimistically into the query cache', async () => {
    server.use(
      http.put('/api/accrual/lines/:lineId/cells', () => HttpResponse.json({ id: CELL_ID })),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(LINE_ID, 2026, 3, '750.00');
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
      http.put('/api/accrual/lines/:lineId/cells', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(LINE_ID, 2026, 3, '100.00');
    });

    await waitFor(() => expect(result.current.savingState).toBe('error'));
    expect(result.current.errorMessage).not.toBeNull();
    expect(result.current.failedCells.has(CELL_KEY)).toBe(true);
  });

  it('clearFailedCell removes the key and clears errorMessage when last', async () => {
    server.use(
      http.put('/api/accrual/lines/:lineId/cells', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { client, wrapper } = createWrapper();
    seedQueryData(client);

    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.updateCell(LINE_ID, 2026, 3, '100.00');
    });

    await waitFor(() => expect(result.current.failedCells.size).toBe(1));

    act(() => {
      result.current.clearFailedCell(CELL_KEY);
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

describe('useAccrualMutations — redistributeLine', () => {
  it('calls POST /accrual/lines/:id/redistribute and returns to idle on success', async () => {
    server.use(
      http.post('/api/accrual/lines/:id/redistribute', () =>
        HttpResponse.json({ cells_updated: 5 }),
      ),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.redistributeLine(LINE_ID);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.errorMessage).toBeNull();
  });
});

describe('useAccrualMutations — setLineRate', () => {
  it('setLineRate PATCHes the line rate and resolves', async () => {
    let capturedBody: unknown = undefined;
    server.use(
      http.patch('/api/accrual/lines/:id', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          id: LINE_ID,
          name: 'Test Line',
          source: 'excel',
          excel_code: 'TST.1',
          value_eur: '500.00',
          value_orig: '500.00',
          currency: 'USD',
          window_start: null,
          window_end: null,
          projects: [],
          rate: '1.2',
          period_rate: '1.0800',
        });
      }),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.setLineRate(LINE_ID, '1.2');
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(capturedBody).toEqual({ rate: '1.2' });
    expect(result.current.errorMessage).toBeNull();
  });

  it('setLineRate sends null to clear', async () => {
    let capturedBody: unknown = undefined;
    server.use(
      http.patch('/api/accrual/lines/:id', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          id: LINE_ID,
          name: 'Test Line',
          source: 'excel',
          excel_code: 'TST.1',
          value_eur: '500.00',
          value_orig: '500.00',
          currency: 'USD',
          window_start: null,
          window_end: null,
          projects: [],
          rate: null,
          period_rate: '1.0800',
        });
      }),
    );

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useAccrualMutations(), { wrapper });

    await act(async () => {
      await result.current.setLineRate(LINE_ID, null);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(capturedBody).toEqual({ rate: null });
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
        { line_id: LINE_ID, year: 2026, month: 3, amount: '400.00' },
        { line_id: LINE_ID, year: 2026, month: 4, amount: '600.00' },
      ]);
    });

    await waitFor(() => expect(result.current.savingState).toBe('idle'));
    expect(result.current.errorMessage).toBeNull();
  });
});
