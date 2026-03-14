import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { projectsApi, projectsCoreApi } from '@/core/services/projects';
import type { ProjectCreate, ProjectListParams, ProjectUpdate, ProjectStatus } from '@/core/types/project';
import { queryKeys } from '@/core/hooks/queryKeys';

export function usePaginatedProjects(params: ProjectListParams) {
  return useQuery({
    queryKey: queryKeys.projects.scorecardList(params),
    queryFn: () => projectsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useProjectSummaries() {
  return useQuery({
    queryKey: queryKeys.projects.scorecardSummary,
    queryFn: projectsApi.listSummary,
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

// --- Core /api/projects hooks ---

export function useCoreProjects(params: ProjectListParams) {
  return useQuery({
    queryKey: queryKeys.projects.list(params),
    queryFn: () => projectsCoreApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCoreProject(id: string) {
  return useQuery({
    queryKey: queryKeys.projects.detail(id),
    queryFn: () => projectsCoreApi.get(id),
    enabled: !!id,
  });
}

export function useCreateCoreProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsCoreApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}

export function useReplaceCoreProject(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsCoreApi.replace(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(id) });
    },
  });
}

export function useDeleteCoreProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => projectsCoreApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}
