import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { snapshotsApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type { SnapshotCreate } from '../types';

export function useProjectSnapshots(projectId: string, limit = 12) {
  return useQuery({
    queryKey: queryKeys.snapshots.byProject(projectId),
    queryFn: () => snapshotsApi.getProjectSnapshots(projectId, limit),
    enabled: !!projectId,
  });
}

export function useSnapshot(projectId: string, year: number, month: number) {
  return useQuery({
    queryKey: queryKeys.snapshots.detail(projectId, year, month),
    queryFn: () => snapshotsApi.getSnapshot(projectId, year, month),
    enabled: !!projectId && !!year && !!month,
  });
}

export function useCreateSnapshot(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SnapshotCreate) =>
      snapshotsApi.createSnapshot(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.snapshots.byProject(projectId),
      });
    },
  });
}

export function useDeleteSnapshot(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (snapshotId: string) => snapshotsApi.deleteSnapshot(snapshotId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.snapshots.byProject(projectId),
      });
    },
  });
}
