import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/core/services/client';
import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '../services/portfolio';
import type { OverviewDecision } from '../types/portfolio';

export interface ProgramOption {
  id: string;
  name: string;
}

export function usePrograms() {
  return useQuery({
    queryKey: ['programs', 'options'],
    queryFn: async (): Promise<ProgramOption[]> => {
      const res = await api.get<ProgramOption[]>('/programs');
      return res.data;
    },
  });
}

export function useUploadOverview() {
  return useMutation({
    mutationFn: (file: File) => portfolioApi.import.upload(file),
  });
}

export function useOverviewMatches(batchId: string | null) {
  return useQuery({
    queryKey: queryKeys.portfolio.import.matches(batchId ?? ''),
    queryFn: () => portfolioApi.import.matches(batchId as string),
    enabled: !!batchId,
  });
}

export function useApplyOverview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, decisions }: { batchId: string; decisions: OverviewDecision[] }) =>
      portfolioApi.import.apply(batchId, decisions),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.portfolio.all });
    },
  });
}
