import { useCallback, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import { buildCellKey } from '@/modules/accrual/types/accrual';
import type { AccrualGridResponse, BulkCellUpdate } from '@/modules/accrual/types/accrual';

type SavingState = 'idle' | 'saving' | 'error';

export interface UseAccrualMutationsReturn {
  updateCell: (cellId: string, amount: string) => Promise<void>;
  bulkUpdate: (updates: BulkCellUpdate[]) => Promise<void>;
  clearOverride: (cellId: string) => Promise<void>;
  redistribute: (projectId: string, force?: boolean) => Promise<void>;
  savingState: SavingState;
  failedCells: ReadonlySet<string>;
  clearFailedCell: (key: string) => void;
  errorMessage: string | null;
}

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === 'string') return err;
  return 'Failed to save changes';
}

function applyAmountToCells(
  prev: AccrualGridResponse | undefined,
  cellId: string,
  amount: string,
): AccrualGridResponse | undefined {
  if (!prev) return prev;
  return {
    ...prev,
    cells: prev.cells.map((c) =>
      c.id === cellId ? { ...c, amount, is_manual_override: true } : c,
    ),
  };
}

export function useAccrualMutations(): UseAccrualMutationsReturn {
  const queryClient = useQueryClient();
  const [savingState, setSavingState] = useState<SavingState>('idle');
  const [failedCells, setFailedCells] = useState<Set<string>>(() => new Set());
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const invalidateGrid = useCallback((): void => {
    queryClient.invalidateQueries({ queryKey: queryKeys.accrual.cells.all });
  }, [queryClient]);

  const patchMutation = useMutation({
    mutationFn: ({ cellId, amount }: { cellId: string; amount: string; cellKey: string }) =>
      accrualApi.cells.patch(cellId, amount),
    onMutate: async ({ cellId, amount }) => {
      setSavingState('saving');
      // Apply optimistic update to all cached grid queries
      queryClient.setQueriesData<AccrualGridResponse>(
        { queryKey: queryKeys.accrual.cells.all },
        (prev) => applyAmountToCells(prev, cellId, amount),
      );
    },
    onSuccess: (_data, { cellKey }) => {
      setSavingState('idle');
      setFailedCells((prev) => {
        if (!prev.has(cellKey)) return prev;
        const next = new Set(prev);
        next.delete(cellKey);
        if (next.size === 0) setErrorMessage(null);
        return next;
      });
      invalidateGrid();
    },
    onError: (err, { cellKey }) => {
      setSavingState('error');
      setErrorMessage(extractErrorMessage(err));
      setFailedCells((prev) => {
        const next = new Set(prev);
        next.add(cellKey);
        return next;
      });
      invalidateGrid();
    },
  });

  const clearOverrideMutation = useMutation({
    mutationFn: (cellId: string) => accrualApi.cells.clearOverride(cellId),
    onMutate: () => setSavingState('saving'),
    onSuccess: () => {
      setSavingState('idle');
      invalidateGrid();
    },
    onError: (err) => {
      setSavingState('error');
      setErrorMessage(extractErrorMessage(err));
      invalidateGrid();
    },
  });

  const redistributeMutation = useMutation({
    mutationFn: ({ projectId, force }: { projectId: string; force?: boolean }) =>
      accrualApi.cells.redistribute(projectId, force),
    onMutate: () => setSavingState('saving'),
    onSuccess: () => {
      setSavingState('idle');
      invalidateGrid();
    },
    onError: (err) => {
      setSavingState('error');
      setErrorMessage(extractErrorMessage(err));
      invalidateGrid();
    },
  });

  const bulkMutation = useMutation({
    mutationFn: (updates: BulkCellUpdate[]) => accrualApi.cells.bulk(updates),
    onMutate: () => setSavingState('saving'),
    onSuccess: () => {
      setSavingState('idle');
      invalidateGrid();
    },
    onError: (err) => {
      setSavingState('error');
      setErrorMessage(extractErrorMessage(err));
      invalidateGrid();
    },
  });

  const updateCell = useCallback(
    async (cellId: string, amount: string): Promise<void> => {
      // Find the cell in any cached grid to build the failedCells key
      const allGridData = queryClient.getQueriesData<AccrualGridResponse>({
        queryKey: queryKeys.accrual.cells.all,
      });
      let cellKey = cellId; // fallback if not cached yet
      for (const [, data] of allGridData) {
        if (!data) continue;
        const found = data.cells.find((c) => c.id === cellId);
        if (found) {
          cellKey = buildCellKey(found.project_id, found.year, found.month);
          break;
        }
      }
      try {
        await patchMutation.mutateAsync({ cellId, amount, cellKey });
      } catch {
        // Error captured in onError; swallow so callers can fire-and-forget
      }
    },
    [queryClient, patchMutation],
  );

  const clearOverride = useCallback(
    async (cellId: string): Promise<void> => {
      try {
        await clearOverrideMutation.mutateAsync(cellId);
      } catch {
        // Error captured in onError
      }
    },
    [clearOverrideMutation],
  );

  const redistribute = useCallback(
    async (projectId: string, force?: boolean): Promise<void> => {
      try {
        await redistributeMutation.mutateAsync({ projectId, force });
      } catch {
        // Error captured in onError
      }
    },
    [redistributeMutation],
  );

  const bulkUpdate = useCallback(
    async (updates: BulkCellUpdate[]): Promise<void> => {
      try {
        await bulkMutation.mutateAsync(updates);
      } catch {
        // Error captured in onError
      }
    },
    [bulkMutation],
  );

  const clearFailedCell = useCallback((key: string): void => {
    setFailedCells((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      if (next.size === 0) setErrorMessage(null);
      return next;
    });
  }, []);

  return {
    updateCell,
    bulkUpdate,
    clearOverride,
    redistribute,
    savingState,
    failedCells,
    clearFailedCell,
    errorMessage,
  };
}
