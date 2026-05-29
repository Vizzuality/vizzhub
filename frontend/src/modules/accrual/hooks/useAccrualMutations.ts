import { useCallback, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import { buildCellKey } from '@/modules/accrual/types/accrual';
import type { AccrualGridResponse, BulkCellUpdate } from '@/modules/accrual/types/accrual';

type SavingState = 'idle' | 'saving' | 'error';

export interface UseAccrualMutationsReturn {
  updateCell: (lineId: string, year: number, month: number, amount: string) => Promise<void>;
  bulkUpdate: (updates: BulkCellUpdate[]) => Promise<void>;
  clearOverride: (cellId: string) => Promise<void>;
  redistributeLine: (lineId: string, force?: boolean) => Promise<void>;
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
  lineId: string,
  year: number,
  month: number,
  amount: string,
): AccrualGridResponse | undefined {
  if (!prev) return prev;
  return {
    ...prev,
    cells: prev.cells.map((c) =>
      c.line_id === lineId && c.year === year && c.month === month
        ? { ...c, amount, is_manual_override: true }
        : c,
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

  // Cells are keyed by (line_id, year, month) — a brand-new cell on an empty
  // month is created server-side, so the same upsert covers create and update.
  const upsertMutation = useMutation({
    mutationFn: ({
      lineId,
      year,
      month,
      amount,
    }: {
      lineId: string;
      year: number;
      month: number;
      amount: string;
      cellKey: string;
    }) => accrualApi.cells.upsertOnLine(lineId, year, month, amount),
    onMutate: async ({ lineId, year, month, amount }) => {
      setSavingState('saving');
      queryClient.setQueriesData<AccrualGridResponse>(
        { queryKey: queryKeys.accrual.cells.all },
        (prev) => applyAmountToCells(prev, lineId, year, month, amount),
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
    mutationFn: ({ lineId, force }: { lineId: string; force?: boolean }) =>
      accrualApi.lines.redistribute(lineId, force),
    ...simpleMutationCallbacks,
  });

  const bulkMutation = useMutation({
    mutationFn: (updates: BulkCellUpdate[]) => accrualApi.cells.bulk(updates),
    ...simpleMutationCallbacks,
  });

  const updateCell = useCallback(
    async (lineId: string, year: number, month: number, amount: string): Promise<void> => {
      const cellKey = buildCellKey(lineId, year, month);
      // Errors captured in onError; swallow so callers can fire-and-forget.
      await upsertMutation
        .mutateAsync({ lineId, year, month, amount, cellKey })
        .catch(() => undefined);
    },
    [upsertMutation],
  );

  // Mutation errors surface via savingState/errorMessage; callers can
  // fire-and-forget without their own try/catch.
  const clearOverride = useCallback(
    (cellId: string): Promise<void> =>
      clearOverrideMutation.mutateAsync(cellId).then(() => undefined).catch(() => undefined),
    [clearOverrideMutation],
  );

  const redistributeLine = useCallback(
    (lineId: string, force?: boolean): Promise<void> =>
      redistributeMutation
        .mutateAsync({ lineId, force })
        .then(() => undefined)
        .catch(() => undefined),
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
    redistributeLine,
    savingState,
    failedCells,
    clearFailedCell,
    errorMessage,
  };
}
