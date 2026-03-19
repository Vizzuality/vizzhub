import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type {
  ProgressReport,
  ProgressReportCreate,
  ProgressReportUpdate,
  BatchProgressResponse,
} from '../types/tracker';

export function useProjectProgress(projectId: string) {
  return useQuery<ProgressReport[]>({
    queryKey: queryKeys.tracker.progress.byProject(projectId),
    queryFn: () => trackerApi.listProgress(projectId),
    enabled: !!projectId,
  });
}

export function useCreateProgress(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProgressReportCreate) =>
      trackerApi.createProgress(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.progress.byProject(projectId),
      });
    },
  });
}

export function useUpdateProgress(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      progressId,
      data,
    }: {
      progressId: string;
      data: ProgressReportUpdate;
    }) => trackerApi.updateProgress(projectId, progressId, data),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.progress.byProject(projectId),
      });
    },
  });
}

export function useDeleteProgress(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (progressId: string) =>
      trackerApi.deleteProgress(projectId, progressId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.progress.byProject(projectId),
      });
    },
  });
}

export function useBatchProgress(projectIds: string[]) {
  return useQuery<BatchProgressResponse>({
    queryKey: queryKeys.tracker.progress.batch(projectIds),
    queryFn: () => trackerApi.getBatchProgress(projectIds),
    enabled: projectIds.length > 0,
  });
}
