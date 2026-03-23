import { useMutation, useQuery, UseQueryResult, UseMutationResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { AnonymousFeedbackCreate, MoodsResponse } from '../types/tracker';

export function useMoods(month: number, year: number): UseQueryResult<MoodsResponse> {
  return useQuery({
    queryKey: queryKeys.tracker.moods(month, year),
    queryFn: () => trackerApi.getMoods(month, year),
  });
}

export function useCreateAnonymousFeedback(): UseMutationResult<void, Error, AnonymousFeedbackCreate> {
  return useMutation({
    mutationFn: (data: AnonymousFeedbackCreate) =>
      trackerApi.createAnonymousFeedback(data),
  });
}
