import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { ReportCreate, ReportPartCreate, ReportPartUpdate } from '../types/tracker';

export function useReports(periodId: string) {
  return useQuery({
    queryKey: queryKeys.tracker.reports.byPeriod(periodId),
    queryFn: () => trackerApi.listReports(periodId),
    enabled: !!periodId,
  });
}

export function useReport(id: string) {
  return useQuery({
    queryKey: queryKeys.tracker.reports.detail(id),
    queryFn: () => trackerApi.getReport(id),
    enabled: !!id,
  });
}

export function useCreateReport(periodId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReportCreate) => trackerApi.createReport(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tracker.reports.byPeriod(periodId),
      });
    },
  });
}

export function useCreateReportPart(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReportPartCreate) => trackerApi.createPart(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tracker.reports.detail(reportId),
      });
    },
  });
}

export function useUpdateReportPart(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ReportPartUpdate }) =>
      trackerApi.updatePart(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tracker.reports.detail(reportId),
      });
    },
  });
}

export function useDeleteReportPart(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trackerApi.deletePart(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tracker.reports.detail(reportId),
      });
    },
  });
}
