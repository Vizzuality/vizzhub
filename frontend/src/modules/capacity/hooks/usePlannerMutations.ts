import { useCallback, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { CellUpdate } from '@/modules/capacity/types/planner';

const DEBOUNCE_MS = 1500;

interface UsePlannerMutationsReturn {
  queueCellUpdate: (update: CellUpdate) => void;
  flushUpdates: () => Promise<void>;
  deleteRow: (projectId: string, userId: string) => Promise<void>;
  isSaving: boolean;
  pendingCount: number;
}

export function usePlannerMutations(
  start: string,
  end: string,
  groupBy: string,
): UsePlannerMutationsReturn {
  const queryClient = useQueryClient();
  const pendingRef = useRef<Map<string, CellUpdate>>(new Map());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cellMutation = useMutation({
    mutationFn: (updates: CellUpdate[]) => plannerApi.updateCells(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      plannerApi.deleteRow(projectId, userId),
    onSuccess: () => {
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
    await cellMutation.mutateAsync(updates);
  }, [cellMutation]);

  const queueCellUpdate = useCallback(
    (update: CellUpdate): void => {
      const key = `${update.project_id}:${update.user_id}:${update.week_start}`;
      pendingRef.current.set(key, update);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        flushUpdates();
      }, DEBOUNCE_MS);
    },
    [flushUpdates],
  );

  const deleteRow = useCallback(
    async (projectId: string, userId: string): Promise<void> => {
      await flushUpdates();
      await deleteMutation.mutateAsync({ projectId, userId });
    },
    [flushUpdates, deleteMutation],
  );

  return {
    queueCellUpdate,
    flushUpdates,
    deleteRow,
    isSaving: cellMutation.isPending || deleteMutation.isPending,
    pendingCount: pendingRef.current.size,
  };
}
