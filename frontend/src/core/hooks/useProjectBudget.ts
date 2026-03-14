import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/core/services/projects';
import { queryKeys } from '@/core/hooks/queryKeys';

interface EVMFormFields {
  budget_total: string;
  cost_to_date: string;
  percent_completed: string;
  percent_planned: string;
}

interface MilestoneFormFields {
  name: string;
  planned_date: string;
  actual_date: string;
}

interface BudgetPayload {
  evm_data?: {
    budget_total?: number;
    cost_to_date?: number;
    percent_completed?: number;
    percent_planned?: number;
  };
  milestones?: Array<{
    name: string;
    planned_date: string;
    actual_date?: string;
  }>;
}

export function buildBudgetPayload(
  evm: EVMFormFields,
  milestones: MilestoneFormFields[],
): BudgetPayload | null {
  const payload: BudgetPayload = {};

  const evmFields: Record<string, number> = {};
  if (evm.budget_total) evmFields.budget_total = Number.parseFloat(evm.budget_total);
  if (evm.cost_to_date) evmFields.cost_to_date = Number.parseFloat(evm.cost_to_date);
  if (evm.percent_completed) {
    evmFields.percent_completed = Number.parseFloat(evm.percent_completed) / 100;
  }
  if (evm.percent_planned) {
    evmFields.percent_planned = Number.parseFloat(evm.percent_planned) / 100;
  }

  if (Object.keys(evmFields).length > 0) {
    payload.evm_data = evmFields;
  }

  const validMilestones = milestones
    .filter((m) => m.name && m.planned_date)
    .map((m) => ({
      name: m.name,
      planned_date: m.planned_date,
      actual_date: m.actual_date || undefined,
    }));

  if (validMilestones.length > 0) {
    payload.milestones = validMilestones;
  }

  if (!payload.evm_data && !payload.milestones) return null;
  return payload;
}

export function useCurrentPeriodMetrics(projectId: string) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  return useQuery({
    queryKey: queryKeys.metrics.byPeriod(projectId, year, month),
    queryFn: async () => {
      try {
        const { metricsHistoryApi } = await import(
          '@/modules/scorecard/services/metrics'
        );
        return await metricsHistoryApi.getByPeriod(projectId, year, month);
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}

export function useUpdateProjectBudget(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BudgetPayload) => projectsApi.updateBudget(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.metrics.byProject(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.scores.byProject(projectId),
      });
    },
  });
}
