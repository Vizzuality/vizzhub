import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/setup';
import { usePlannerMutations } from '../usePlannerMutations';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const baseUpdate = {
  project_id: 'p1',
  user_id: 'u1',
  week_start: '2026-01-05',
  percentage: 50,
};

describe('usePlannerMutations — error capture', () => {
  it('captures error message and marks the failing cell when save fails', async () => {
    server.use(
      http.patch('/api/capacity/planner/cells', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { result } = renderHook(
      () => usePlannerMutations('2026-01-05', '2026-04-06', 'project'),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.queueCellUpdate(baseUpdate);
      await result.current.flushUpdates();
    });

    await waitFor(() => expect(result.current.errorMessage).not.toBeNull());
    expect(result.current.failedCells.has('p1:u1:2026-01-05')).toBe(true);
  });

  it('clears the failed cell when the user edits it again', async () => {
    server.use(
      http.patch('/api/capacity/planner/cells', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { result } = renderHook(
      () => usePlannerMutations('2026-01-05', '2026-04-06', 'project'),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.queueCellUpdate(baseUpdate);
      await result.current.flushUpdates();
    });

    await waitFor(() => expect(result.current.failedCells.size).toBe(1));

    act(() => {
      result.current.queueCellUpdate({ ...baseUpdate, percentage: 60 });
    });

    expect(result.current.failedCells.has('p1:u1:2026-01-05')).toBe(false);
    expect(result.current.errorMessage).toBeNull();
  });

  it('clearError resets state', async () => {
    server.use(
      http.patch('/api/capacity/planner/cells', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { result } = renderHook(
      () => usePlannerMutations('2026-01-05', '2026-04-06', 'project'),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.queueCellUpdate(baseUpdate);
      await result.current.flushUpdates();
    });

    await waitFor(() => expect(result.current.failedCells.size).toBe(1));

    act(() => result.current.clearError());

    expect(result.current.errorMessage).toBeNull();
    expect(result.current.failedCells.size).toBe(0);
  });

  it('does not surface an error when the save succeeds', async () => {
    server.use(
      http.patch('/api/capacity/planner/cells', () =>
        HttpResponse.json({ updated: 1 }),
      ),
    );

    const { result } = renderHook(
      () => usePlannerMutations('2026-01-05', '2026-04-06', 'project'),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.queueCellUpdate(baseUpdate);
      await result.current.flushUpdates();
    });

    expect(result.current.errorMessage).toBeNull();
    expect(result.current.failedCells.size).toBe(0);
  });
});
