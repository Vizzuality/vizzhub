import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { accrualApi } from '@/modules/accrual/services/accrual';
import type {
  AccrualPeriod,
  AccrualPeriodCreate,
} from '@/modules/accrual/types/accrual';

export function usePeriodsList() {
  return useQuery<AccrualPeriod[]>({
    queryKey: queryKeys.accrual.periods.list(),
    queryFn: () => accrualApi.periods.list(),
  });
}

export function useCurrentPeriod() {
  return useQuery<AccrualPeriod | null>({
    queryKey: queryKeys.accrual.periods.current(),
    queryFn: () => accrualApi.periods.current(),
  });
}

export function useCreatePeriod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AccrualPeriodCreate) => accrualApi.periods.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.accrual.periods.all });
    },
  });
}
