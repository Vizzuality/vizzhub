import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { ReportingPeriodCreate } from '../types/tracker';

export function useReportingPeriods() {
  return useQuery({
    queryKey: queryKeys.tracker.periods.list(),
    queryFn: trackerApi.listPeriods,
  });
}

export function useReportingPeriod(id: string) {
  return useQuery({
    queryKey: queryKeys.tracker.periods.detail(id),
    queryFn: () => trackerApi.getPeriod(id),
    enabled: !!id,
  });
}

export function useCreatePeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReportingPeriodCreate) => trackerApi.createPeriod(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.periods.all });
    },
  });
}

export function useDeletePeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.deletePeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.periods.all });
    },
  });
}

export function useActivatePeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.activatePeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.periods.all });
    },
  });
}

export function useFinishPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.finishPeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.periods.all });
    },
  });
}

export function useReactivatePeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.reactivatePeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tracker.periods.all });
    },
  });
}
