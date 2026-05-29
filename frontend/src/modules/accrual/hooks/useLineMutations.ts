import { useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type { AccrualLineCreate, AccrualLineUpdate } from '@/modules/accrual/types/accrual';

/** Line lifecycle mutations — create/update/delete and project link/unlink.
 * Every success invalidates the grid (cells.all) so rows reflect the change. */
export function useLineMutations() {
  const queryClient = useQueryClient();

  const invalidate = useCallback(
    (lineId?: string): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accrual.cells.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.accrual.lines.all });
      if (lineId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.accrual.lines.detail(lineId) });
      }
    },
    [queryClient],
  );

  const create = useMutation({
    mutationFn: (payload: AccrualLineCreate) => accrualApi.lines.create(payload),
    onSuccess: () => invalidate(),
  });

  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AccrualLineUpdate }) =>
      accrualApi.lines.update(id, payload),
    onSuccess: (_data, { id }) => invalidate(id),
  });

  const remove = useMutation({
    mutationFn: (id: string) => accrualApi.lines.remove(id),
    onSuccess: () => invalidate(),
  });

  const linkProject = useMutation({
    mutationFn: ({ id, projectId }: { id: string; projectId: string }) =>
      accrualApi.lines.linkProject(id, projectId),
    onSuccess: (_data, { id }) => invalidate(id),
  });

  const unlinkProject = useMutation({
    mutationFn: ({ id, projectId }: { id: string; projectId: string }) =>
      accrualApi.lines.unlinkProject(id, projectId),
    onSuccess: (_data, { id }) => invalidate(id),
  });

  return { create, update, remove, linkProject, unlinkProject };
}
