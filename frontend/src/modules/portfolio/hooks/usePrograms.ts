import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';

import { queryKeys } from '@/core/hooks/queryKeys';
import { projectsApi } from '@/core/services/projects';
import { portfolioApi } from '@/modules/portfolio/services/portfolio';
import type {
  ProgramIndexFilters,
  ProgramIndexResponse,
  ProgramOption,
  ProgramProfileUpdate,
  ProgramSummary,
  ProgramTermsUpdate,
  ProjectIteration,
} from '@/modules/portfolio/types/portfolio';

export function useProgramIndex(
  filters: ProgramIndexFilters,
): UseQueryResult<ProgramIndexResponse> {
  return useQuery<ProgramIndexResponse>({
    queryKey: queryKeys.portfolio.programs.index(filters as Record<string, unknown>),
    queryFn: () => portfolioApi.programs.index(filters),
    placeholderData: keepPreviousData,
  });
}

export function useProgramDetail(id: string | undefined): UseQueryResult<ProgramSummary> {
  return useQuery<ProgramSummary>({
    queryKey: queryKeys.portfolio.programs.detail(id ?? ''),
    queryFn: () => portfolioApi.programs.detail(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useProgramOptions(): UseQueryResult<ProgramOption[]> {
  return useQuery<ProgramOption[]>({
    queryKey: queryKeys.portfolio.programs.options(),
    queryFn: () => portfolioApi.programs.options(),
    staleTime: 5 * 60 * 1000,
  });
}

function useInvalidatePrograms(): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.programs.all });
  };
}

export function useCreateProgram() {
  const invalidate = useInvalidatePrograms();
  return useMutation({
    mutationFn: (name: string) => portfolioApi.programs.create(name),
    onSuccess: invalidate,
  });
}

export function useRenameProgram(id: string) {
  const invalidate = useInvalidatePrograms();
  return useMutation({
    mutationFn: (name: string) => portfolioApi.programs.rename(id, name),
    onSuccess: invalidate,
  });
}

export function useUpdateProgramProfile(id: string) {
  const invalidate = useInvalidatePrograms();
  return useMutation({
    mutationFn: (data: ProgramProfileUpdate) => portfolioApi.programs.updateProfile(id, data),
    onSuccess: invalidate,
  });
}

export function useReplaceProgramTerms(id: string) {
  const invalidate = useInvalidatePrograms();
  return useMutation({
    mutationFn: (data: ProgramTermsUpdate) => portfolioApi.programs.replaceTerms(id, data),
    onSuccess: invalidate,
  });
}

export function useUnassignedProjects(): UseQueryResult<ProjectIteration[]> {
  return useQuery<ProjectIteration[]>({
    queryKey: queryKeys.portfolio.programs.unassigned(),
    queryFn: () => portfolioApi.programs.unassigned(),
  });
}

export function useStageOptions(): UseQueryResult<string[]> {
  return useQuery<string[]>({
    queryKey: queryKeys.portfolio.programs.stages(),
    queryFn: () => portfolioApi.programs.stages(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSetProjectProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, programId }: { projectId: string; programId: string | null }) =>
      projectsApi.update(projectId, { program_id: programId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.programs.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
    },
  });
}
