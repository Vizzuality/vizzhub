import { useCallback, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { CellUpdate, PlannerResponse } from '@/modules/capacity/types/planner';

const DEBOUNCE_MS = 800;

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
  const [pendingCount, setPendingCount] = useState(0);

  const cellMutation = useMutation({
    mutationFn: (updates: CellUpdate[]) => plannerApi.updateCells(updates),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      plannerApi.deleteRow(projectId, userId),
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
    await cellMutation.mutateAsync(updates);
  }, [cellMutation]);

  const applyOptimisticUpdate = useCallback(
    (update: CellUpdate): void => {
      const qk = queryKeys.capacity.planner(start, end, groupBy);
      queryClient.setQueryData<PlannerResponse>(qk, (prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          groups: prev.groups.map((g) => ({
            ...g,
            rows: g.rows.map((r) => {
              if (r.project_id !== update.project_id || r.user_id !== update.user_id) return r;
              const cells = { ...r.cells };
              if (update.percentage === null) {
                delete cells[update.week_start];
              } else {
                cells[update.week_start] = update.percentage;
              }
              return { ...r, cells };
            }),
          })),
        };
      });
    },
    [queryClient, start, end, groupBy],
  );

  const queueCellUpdate = useCallback(
    (update: CellUpdate): void => {
      const key = `${update.project_id}:${update.user_id}:${update.week_start}`;
      pendingRef.current.set(key, update);
      setPendingCount(pendingRef.current.size);
      applyOptimisticUpdate(update);

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
      await deleteMutation.mutateAsync({ projectId, userId });
    },
    [flushUpdates, deleteMutation],
  );

  return {
    queueCellUpdate,
    flushUpdates,
    deleteRow,
    isSaving: cellMutation.isPending || deleteMutation.isPending,
    pendingCount,
  };
}
