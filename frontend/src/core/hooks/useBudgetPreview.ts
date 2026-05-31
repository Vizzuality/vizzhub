import { useEffect, useState } from 'react';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { projectsApi } from '@/core/services/projects';
import type { BudgetPreviewResponse } from '@/types';

interface BudgetPreviewInputs {
  originalBudget: string;
  currency: string;
  startDate: string;
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export function useBudgetPreview(
  inputs: BudgetPreviewInputs,
): UseQueryResult<BudgetPreviewResponse> {
  const originalBudget = useDebouncedValue(inputs.originalBudget, 350);
  const currency = useDebouncedValue(inputs.currency, 350);
  const startDate = useDebouncedValue(inputs.startDate, 350);

  const amount = Number.parseFloat(originalBudget);
  const enabled = Number.isFinite(amount) && amount > 0 && !!currency && !!startDate;

  return useQuery({
    queryKey: queryKeys.projects.budgetPreview(amount, currency, startDate),
    queryFn: () =>
      projectsApi.budgetPreview({
        original_budget: amount,
        currency,
        start_date: startDate,
      }),
    enabled,
    staleTime: 60_000,
    gcTime: 0,
  });
}
