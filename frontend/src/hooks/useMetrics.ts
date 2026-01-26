import { useQuery, useMutation, useQueryClient, QueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { MetricsCreate, EVMData, Milestone, StrategicImpact } from '../types';
import { queryKeys } from './queryKeys';

interface Metrics extends MetricsCreate {
  id: string;
  project_id: string;
  created_at: string;
}

export function useProjectMetrics(projectId: string) {
  return useQuery({
    queryKey: queryKeys.metrics.byProject(projectId),
    queryFn: async (): Promise<Metrics | null> => {
      try {
        const response = await api.get<Metrics[]>(`/metrics/project/${projectId}`);
        if (response.data && response.data.length > 0) {
          const sorted = response.data.sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
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

function createMetricsMutation<T>(
  projectId: string,
  existingMetrics: Metrics | null,
  fieldName: MetricsField,
  queryClient: QueryClient,
) {
  return async (value: T): Promise<Metrics> => {
    const today = new Date().toISOString().split('T')[0];
    const metrics: MetricsCreate = {
      period_start: existingMetrics?.period_start ?? today,
      period_end: today,
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
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMetricsMutation<T>(projectId, existingMetrics, fieldName, queryClient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics.byProject(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.byProject(projectId) });
    },
  });
}

export function useUpdateEVMData(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<EVMData>(projectId, existingMetrics, 'evm_data');
}

export function useUpdateMilestones(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<Milestone[]>(projectId, existingMetrics, 'milestones');
}

export function useUpdateGovernance(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<number>(projectId, existingMetrics, 'governance_exceptions');
}

interface PMSatisfactionInput {
  delivery_complaints: 'yes' | 'no' | '-';
  design_complaints: 'yes' | 'no' | '-';
  overall_estimation?: number;
}

export function useUpdatePMSatisfaction(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<PMSatisfactionInput>(projectId, existingMetrics, 'pm_satisfaction');
}

interface TestMaturityInput {
  e2e?: number;
  unit?: number;
  accessibility?: number;
  security?: number;
  frontend?: number;
}

export function useUpdateTestMaturity(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<TestMaturityInput>(projectId, existingMetrics, 'test_maturity');
}

interface ArchitectureInput {
  docs_up_to_date: boolean;
  iac_implemented: boolean;
  adrs_maintained: boolean;
  diagrams_updated: boolean;
}

export function useUpdateArchitecture(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<ArchitectureInput>(projectId, existingMetrics, 'architecture');
}

export function useUpdateStrategicImpact(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<StrategicImpact>(projectId, existingMetrics, 'strategic_impact');
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

export function useUpdateClientSurvey(projectId: string, existingMetrics: Metrics | null) {
  return useMetricsFieldMutation<ClientSurveyInput>(projectId, existingMetrics, 'client_survey');
}
