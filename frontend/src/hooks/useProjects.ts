import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '../services/api';
import type { ProjectCreate, ProjectUpdate, ProjectStatus } from '../types';
import { queryKeys } from './queryKeys';

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.all,
    queryFn: projectsApi.list,
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
      if (params.status === 'in_progress') {
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
