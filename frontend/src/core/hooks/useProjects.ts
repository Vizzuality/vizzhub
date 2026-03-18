import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { projectsApi } from '@/core/services/projects';
import type { ProjectCreate, ProjectListParams, ProjectUpdate, ProjectStatus } from '@/core/types/project';
import { queryKeys } from '@/core/hooks/queryKeys';

export function usePaginatedProjects(params: ProjectListParams) {
  return useQuery({
    queryKey: queryKeys.projects.scorecardList(params),
    queryFn: () => projectsApi.listScorecard(params),
    placeholderData: keepPreviousData,
  });
}

export function usePaginatedAllProjects(params: ProjectListParams) {
  return useQuery({
    queryKey: queryKeys.projects.list(params),
    queryFn: () => projectsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useProjectSummaries() {
  return useQuery({
    queryKey: queryKeys.projects.scorecardSummary,
    queryFn: projectsApi.listScorecardSummary,
  });
}

export function useAllProjectSummaries() {
  return useQuery({
    queryKey: queryKeys.projects.allSummary,
    queryFn: projectsApi.listAllSummary,
  });
}

export function useActiveProjectSummaries() {
  return useQuery({
    queryKey: queryKeys.projects.activeSummary,
    queryFn: projectsApi.listActiveSummary,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id),
    queryFn: () => projectsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectUpdate) => projectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(id) });
    },
  });
}

export function useReplaceProject(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.replace(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(id) });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}

interface UpdateStatusParams {
  status: ProjectStatus;
  finished_at?: string;
}

export function useUpdateProjectStatus(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: UpdateStatusParams) => {
      if (params.status === 'live') {
        return projectsApi.update(id, { status: params.status, clear_finished_at: true });
      }
      return projectsApi.update(id, { status: params.status, finished_at: params.finished_at });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(id) });
    },
  });
}
