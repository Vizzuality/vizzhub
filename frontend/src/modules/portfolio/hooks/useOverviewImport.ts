import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '../services/portfolio';
import type { OverviewDecisionPatch } from '../types/portfolio';

export function useUploadOverview() {
  return useMutation({
    mutationFn: (file: File) => portfolioApi.import.upload(file),
  });
}

export function useCurrentImportBatch() {
  return useQuery({
    queryKey: queryKeys.portfolio.import.current,
    queryFn: () => portfolioApi.import.current(),
  });
}

export function useImportProjects() {
  return useQuery({
    queryKey: queryKeys.portfolio.import.projects,
    queryFn: () => portfolioApi.import.projects(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useOverviewMatches(batchId: string | null) {
  return useQuery({
    queryKey: queryKeys.portfolio.import.matches(batchId ?? ''),
    queryFn: () => portfolioApi.import.matches(batchId as string),
    enabled: !!batchId,
  });
}

export function useSaveDecision() {
  return useMutation({
    mutationFn: ({
      batchId,
      stagingId,
      patch,
    }: {
      batchId: string;
      stagingId: string;
      patch: OverviewDecisionPatch;
    }) => portfolioApi.import.saveDecision(batchId, stagingId, patch),
  });
}

export function useApplyOverview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => portfolioApi.import.apply(batchId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.portfolio.all });
      qc.invalidateQueries({ queryKey: queryKeys.portfolio.import.current });
    },
  });
}
