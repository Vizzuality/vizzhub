import { useCallback, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { CellUpdate, PlannerResponse, PlannerRow } from '@/modules/capacity/types/planner';

const DEBOUNCE_MS = 800;

function updateRowCells(row: PlannerRow, update: CellUpdate): PlannerRow {
  if (row.project_id !== update.project_id || row.user_id !== update.user_id) return row;
  const cells = { ...row.cells };
  const comments = { ...row.comments };
  if (update.percentage === null) {
    delete cells[update.week_start];
    delete comments[update.week_start];
  } else {
    cells[update.week_start] = update.percentage;
    if (update.comment === null) {
      delete comments[update.week_start];
    } else if (update.comment !== undefined) {
      comments[update.week_start] = update.comment;
    }
  }
  return { ...row, cells, comments };
}

function applyUpdateToResponse(prev: PlannerResponse, update: CellUpdate): PlannerResponse {
  return {
    ...prev,
    groups: prev.groups.map((g) => ({
      ...g,
      rows: g.rows.map((r) => updateRowCells(r, update)),
    })),
  };
}

function cellKey(update: Pick<CellUpdate, 'project_id' | 'user_id' | 'week_start'>): string {
  return `${update.project_id}:${update.user_id}:${update.week_start}`;
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === 'string') return err;
  return 'Failed to save changes';
}

interface UsePlannerMutationsReturn {
  queueCellUpdate: (update: CellUpdate) => void;
  flushUpdates: () => Promise<void>;
  deleteRow: (projectId: string, userId: string) => Promise<void>;
  isSaving: boolean;
  pendingCount: number;
  errorMessage: string | null;
  failedCells: ReadonlySet<string>;
  clearError: () => void;
}

export function usePlannerMutations(
  start: string,
  end: string,
  groupBy: string,
): UsePlannerMutationsReturn {
  const queryClient = useQueryClient();
  const pendingRef = useRef<Map<string, CellUpdate>>(new Map());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [failedCells, setFailedCells] = useState<Set<string>>(() => new Set());

  const clearError = useCallback((): void => {
    setErrorMessage(null);
    setFailedCells(new Set());
  }, []);

  const cellMutation = useMutation({
    mutationFn: (updates: CellUpdate[]) => plannerApi.updateCells(updates),
    onSuccess: (_data, updates) => {
      if (updates.length === 0) return;
      setFailedCells((prev) => {
        if (prev.size === 0) return prev;
        const next = new Set(prev);
        let changed = false;
        for (const u of updates) {
          if (next.delete(cellKey(u))) changed = true;
        }
        if (!changed) return prev;
        if (next.size === 0) setErrorMessage(null);
        return next;
      });
    },
    onError: (err, updates) => {
      setErrorMessage(extractErrorMessage(err));
      setFailedCells((prev) => {
        const next = new Set(prev);
        for (const u of updates) next.add(cellKey(u));
        return next;
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      plannerApi.deleteRow(projectId, userId),
    onError: (err) => {
      setErrorMessage(extractErrorMessage(err));
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const flushUpdates = useCallback(async (): Promise<void> => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const updates = Array.from(pendingRef.current.values());
    if (updates.length === 0) return;
    pendingRef.current.clear();
    setPendingCount(0);
    try {
      await cellMutation.mutateAsync(updates);
    } catch {
      // Error state is captured in onError; swallow so flush callers
      // (navigate, group-by change) don't crash.
    }
  }, [cellMutation]);

  const applyOptimisticUpdate = useCallback(
    (update: CellUpdate): void => {
      const qk = queryKeys.capacity.planner(start, end, groupBy);
      queryClient.setQueryData<PlannerResponse>(qk, (prev) => {
        if (!prev) return prev;
        return applyUpdateToResponse(prev, update);
      });
    },
    [queryClient, start, end, groupBy],
  );

  const queueCellUpdate = useCallback(
    (update: CellUpdate): void => {
      const key = cellKey(update);
      const existing = pendingRef.current.get(key);
      const merged = existing && update.comment === undefined
        ? { ...update, comment: existing.comment }
        : update;
      pendingRef.current.set(key, merged);
      setPendingCount(pendingRef.current.size);
      applyOptimisticUpdate(update);

      setFailedCells((prev) => {
        if (!prev.has(key)) return prev;
        const next = new Set(prev);
        next.delete(key);
        if (next.size === 0) setErrorMessage(null);
        return next;
      });

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        flushUpdates();
      }, DEBOUNCE_MS);
    },
    [flushUpdates, applyOptimisticUpdate],
  );

  const deleteRow = useCallback(
    async (projectId: string, userId: string): Promise<void> => {
      await flushUpdates();
      try {
        await deleteMutation.mutateAsync({ projectId, userId });
      } catch {
        // Error captured via onError; rethrowing would break callers
        // that fire-and-forget delete on confirm-dialog action.
      }
    },
    [flushUpdates, deleteMutation],
  );

  return {
    queueCellUpdate,
    flushUpdates,
    deleteRow,
    isSaving: cellMutation.isPending || deleteMutation.isPending,
    pendingCount,
    errorMessage,
    failedCells,
    clearError,
  };
}
