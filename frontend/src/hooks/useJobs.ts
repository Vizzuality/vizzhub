import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type {
  CreateCaptureHistoryJobRequest,
  JobDetailResponse,
  JobResponse,
  JobSummaryResponse,
} from '../types';

interface UseJobStatusOptions {
  enabled?: boolean;
}

/**
 * Hook for polling job status.
 * Automatically polls every 3s while job is pending/running.
 */
export function useJobStatus(
  jobId: string | null,
  options: UseJobStatusOptions = {},
): ReturnType<typeof useQuery<JobDetailResponse, Error>> {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId!),
    queryFn: (): Promise<JobDetailResponse> => jobsApi.getJob(jobId!),
    enabled: !!jobId && options.enabled !== false,
    refetchInterval: (query): number | false => {
      const status = query.state.data?.status;
      if (status === 'pending' || status === 'running') {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Hook for creating a historical capture job.
 */
export function useCaptureHistoryJob(
  projectId: string,
): ReturnType<typeof useMutation<JobResponse, Error, Omit<CreateCaptureHistoryJobRequest, 'project_id'>>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      request: Omit<CreateCaptureHistoryJobRequest, 'project_id'>,
    ): Promise<JobResponse> =>
      jobsApi.createCaptureHistory({ ...request, project_id: projectId }),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.byProject(projectId) });
    },
  });
}

/**
 * Hook for listing jobs for a project.
 */
export function useProjectJobs(
  projectId: string,
): ReturnType<typeof useQuery<JobSummaryResponse[], Error>> {
  return useQuery({
    queryKey: queryKeys.jobs.byProject(projectId),
    queryFn: (): Promise<JobSummaryResponse[]> => jobsApi.listJobs(projectId),
  });
}

/**
 * Hook for listing all jobs across all projects.
 * Polls every 5s to show active job progress.
 */
export function useAllJobs(): ReturnType<typeof useQuery<JobSummaryResponse[], Error>> {
  return useQuery({
    queryKey: queryKeys.jobs.all,
    queryFn: (): Promise<JobSummaryResponse[]> => jobsApi.listJobs(),
    refetchInterval: 5000,
  });
}

/**
 * Hook for cancelling a job.
 */
export function useCancelJob(): ReturnType<typeof useMutation<JobResponse, Error, string>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string): Promise<JobResponse> => jobsApi.cancelJob(jobId),
    onSuccess: (data): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
  });
}

/**
 * Hook for deleting a job.
 */
export function useDeleteJob(): ReturnType<typeof useMutation<void, Error, string>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string): Promise<void> => jobsApi.deleteJob(jobId),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
  });
}
