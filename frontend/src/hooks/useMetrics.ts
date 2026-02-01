import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { metricsHistoryApi } from '../services/api';
import type { Metrics, MetricsCreate, EVMData, Milestone, StrategicImpact } from '../types';
import { queryKeys } from './queryKeys';
import type { Period } from '../utils/dateUtils';

export function useProjectMetrics(
  projectId: string,
  year?: number,
  month?: number,
) {
  const hasPeriod = year !== undefined && month !== undefined;

  return useQuery({
    queryKey: hasPeriod
      ? queryKeys.metrics.byPeriod(projectId, year, month)
      : queryKeys.metrics.byProject(projectId),
    queryFn: async (): Promise<Metrics | null> => {
      try {
        if (hasPeriod) {
          // Get metrics for specific period
          const response = await metricsHistoryApi.getByPeriod(
            projectId,
            year,
            month,
            'cumulative',
          );
          return response as unknown as Metrics;
        }

        // Default: get latest metrics
        const response = await api.get<Metrics[]>(`/metrics/project/${projectId}`);
        if (response.data && response.data.length > 0) {
          const sorted = response.data.sort((a, b) => {
            return new Date(b.period_end).getTime() - new Date(a.period_end).getTime();
          });
          return sorted[0];
        }
        return null;
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}

export function useCreateMetrics(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (metrics: MetricsCreate): Promise<Metrics> => {
      const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
    },
  });
}

type MetricsField = keyof Omit<MetricsCreate, 'period_start' | 'period_end' | 'sev1_incident'>;

function getPeriodDates(period?: Period | null): { start: string; end: string } {
  if (!period) {
    const today = new Date().toISOString().split('T')[0];
    return { start: today, end: today };
  }
  const start = new Date(period.year, period.month - 1, 1);
  const end = new Date(period.year, period.month, 0);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

function createMetricsMutation<T>(
  projectId: string,
  existingMetrics: Metrics | null,
  fieldName: MetricsField,
  period?: Period | null,
) {
  return async (value: T): Promise<Metrics> => {
    const { start, end } = getPeriodDates(period);
    const metrics: MetricsCreate = {
      period_start: existingMetrics?.period_start ?? start,
      period_end: end,
      evm_data: existingMetrics?.evm_data,
      milestones: existingMetrics?.milestones,
      jira_defects: existingMetrics?.jira_defects,
      flow_metrics: existingMetrics?.flow_metrics,
      github_metrics: existingMetrics?.github_metrics,
      test_maturity: existingMetrics?.test_maturity,
      architecture: existingMetrics?.architecture,
      pm_satisfaction: existingMetrics?.pm_satisfaction,
      client_survey: existingMetrics?.client_survey,
      strategic_impact: existingMetrics?.strategic_impact,
      governance_exceptions: existingMetrics?.governance_exceptions,
      sev1_incident: existingMetrics?.sev1_incident ?? false,
      [fieldName]: value,
    };
    const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
    return response.data;
  };
}

function useMetricsFieldMutation<T>(
  projectId: string,
  existingMetrics: Metrics | null,
  fieldName: MetricsField,
  period?: Period | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMetricsMutation<T>(projectId, existingMetrics, fieldName, period),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
      if (period) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.metrics.byPeriod(projectId, period.year, period.month),
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.scores.byPeriod(projectId, period.year, period.month),
        });
      }
    },
  });
}

export function useUpdateEVMData(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<EVMData>(projectId, existingMetrics, 'evm_data', period);
}

export function useUpdateMilestones(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<Milestone[]>(projectId, existingMetrics, 'milestones', period);
}

export function useUpdateGovernance(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<number>(projectId, existingMetrics, 'governance_exceptions', period);
}

interface PMSatisfactionInput {
  delivery_complaints: 'yes' | 'no' | '-';
  design_complaints: 'yes' | 'no' | '-';
  overall_estimation?: number;
}

export function useUpdatePMSatisfaction(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<PMSatisfactionInput>(projectId, existingMetrics, 'pm_satisfaction', period);
}

interface TestMaturityInput {
  e2e?: number;
  unit?: number;
  accessibility?: number;
  security?: number;
  frontend?: number;
}

export function useUpdateTestMaturity(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<TestMaturityInput>(projectId, existingMetrics, 'test_maturity', period);
}

interface ArchitectureInput {
  docs_up_to_date: boolean;
  iac_implemented: boolean;
  adrs_maintained: boolean;
  diagrams_updated: boolean;
}

export function useUpdateArchitecture(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<ArchitectureInput>(projectId, existingMetrics, 'architecture', period);
}

export function useUpdateStrategicImpact(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<StrategicImpact>(projectId, existingMetrics, 'strategic_impact', period);
}

interface ClientSurveyInput {
  understanding?: number;
  proactivity?: number;
  communication?: number;
  delivery_time?: number;
  response_time?: number;
  quality?: number;
  expectations?: number;
  recommend?: number;
}

export function useUpdateClientSurvey(projectId: string, existingMetrics: Metrics | null, period?: Period | null) {
  return useMetricsFieldMutation<ClientSurveyInput>(projectId, existingMetrics, 'client_survey', period);
}

export type { Period };
