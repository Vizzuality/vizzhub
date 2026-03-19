import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { BudgetLine, BudgetLineCreate } from '../types/tracker';

export function useBudgetLines(projectId: string): {
  data: BudgetLine[] | undefined;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.tracker.budgetLines.byProject(projectId),
    queryFn: () => trackerApi.getBudgetLines(projectId),
    enabled: !!projectId,
  });
  return { data, isLoading };
}

export function useReplaceBudgetLines(projectId: string): {
  mutateAsync: (lines: BudgetLineCreate[]) => Promise<BudgetLine[]>;
  isPending: boolean;
} {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (lines: BudgetLineCreate[]) =>
      trackerApi.replaceBudgetLines(projectId, lines),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.tracker.budgetLines.byProject(projectId),
      });
    },
  });
  return { mutateAsync: mutation.mutateAsync, isPending: mutation.isPending };
}

export function useFunctionalAreas(): {
  data: { id: string; name: string }[] | undefined;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.functionalAreas.all,
    queryFn: () => trackerApi.listFunctionalAreas(),
    staleTime: 5 * 60 * 1000,
  });
  return { data, isLoading };
}
