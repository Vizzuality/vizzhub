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

  const simpleMutationCallbacks = {
    onMutate: () => setSavingState('saving'),
    onSuccess: () => {
      setSavingState('idle');
      invalidateGrid();
    },
    onError: (err: unknown) => {
      setSavingState('error');
      setErrorMessage(extractErrorMessage(err));
      invalidateGrid();
    },
  };

  const clearOverrideMutation = useMutation({
    mutationFn: (cellId: string) => accrualApi.cells.clearOverride(cellId),
    ...simpleMutationCallbacks,
  });

  const redistributeMutation = useMutation({
    mutationFn: ({ projectId, force }: { projectId: string; force?: boolean }) =>
      accrualApi.cells.redistribute(projectId, force),
    ...simpleMutationCallbacks,
  });

  const bulkMutation = useMutation({
    mutationFn: (updates: BulkCellUpdate[]) => accrualApi.cells.bulk(updates),
    ...simpleMutationCallbacks,
  });

  const updateCell = useCallback(
    async (cellId: string, amount: string): Promise<void> => {
      // Find the cell in any cached grid to build the failedCells key.
      const allGridData = queryClient.getQueriesData<AccrualGridResponse>({
        queryKey: queryKeys.accrual.cells.all,
      });
      let cellKey = cellId; // fallback if not cached yet
      for (const [, data] of allGridData) {
        const found = data?.cells.find((c) => c.id === cellId);
        if (found) {
          cellKey = buildCellKey(found.project_id, found.year, found.month);
          break;
        }
      }
      // Errors captured in onError; swallow so callers can fire-and-forget.
      await patchMutation.mutateAsync({ cellId, amount, cellKey }).catch(() => undefined);
    },
    [queryClient, patchMutation],
  );

  // Mutation errors surface via savingState/errorMessage; callers can
  // fire-and-forget without their own try/catch.
  const clearOverride = useCallback(
    (cellId: string): Promise<void> =>
      clearOverrideMutation.mutateAsync(cellId).then(() => undefined).catch(() => undefined),
    [clearOverrideMutation],
  );

  const redistribute = useCallback(
    (projectId: string, force?: boolean): Promise<void> =>
      redistributeMutation.mutateAsync({ projectId, force }).then(() => undefined).catch(() => undefined),
    [redistributeMutation],
  );

  const bulkUpdate = useCallback(
    (updates: BulkCellUpdate[]): Promise<void> =>
      bulkMutation.mutateAsync(updates).then(() => undefined).catch(() => undefined),
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
