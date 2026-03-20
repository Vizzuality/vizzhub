import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type {
  NonStaffCost,
  NonStaffCostCreate,
  NonStaffCostUpdate,
} from '../types/tracker';

export function useNonStaffCosts(projectId: string) {
  return useQuery<NonStaffCost[]>({
    queryKey: queryKeys.tracker.nonStaffCosts.byProject(projectId),
    queryFn: () => trackerApi.listNonStaffCosts(projectId),
    enabled: !!projectId,
  });
}

export function useCreateNonStaffCost(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NonStaffCostCreate) =>
      trackerApi.createNonStaffCost(data),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.nonStaffCosts.byProject(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.projectCosts.summary(projectId),
      });
    },
  });
}

export function useUpdateNonStaffCost(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ costId, data }: { costId: string; data: NonStaffCostUpdate }) =>
      trackerApi.updateNonStaffCost(costId, data),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.nonStaffCosts.byProject(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.projectCosts.summary(projectId),
      });
    },
  });
}

export function useDeleteNonStaffCost(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (costId: string) =>
      trackerApi.deleteNonStaffCost(costId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.nonStaffCosts.byProject(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.tracker.projectCosts.summary(projectId),
      });
    },
  });
}
