import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { AnonymousFeedbackCreate } from '../types/tracker';

export function useMoods(month: number, year: number) {
  return useQuery({
    queryKey: queryKeys.tracker.moods(month, year),
    queryFn: () => trackerApi.getMoods(month, year),
  });
}

export function useCreateAnonymousFeedback() {
  return useMutation({
    mutationFn: (data: AnonymousFeedbackCreate) =>
      trackerApi.createAnonymousFeedback(data),
  });
}

export function useDeleteAnonymousFeedback(month: number, year: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.deleteAnonymousFeedback(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.moods(month, year) });
    },
  });
}

export function useMoodsTrend() {
  return useQuery({
    queryKey: queryKeys.tracker.moodsTrend,
    queryFn: () => trackerApi.getMoodsTrend(),
  });
}

export function useDeleteReportMood(month: number, year: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reportId: string) => trackerApi.deleteReportMood(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.moods(month, year) });
    },
  });
}
