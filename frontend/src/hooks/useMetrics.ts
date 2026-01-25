import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { MetricsCreate, EVMData, Milestone } from '../types';

interface Metrics extends MetricsCreate {
  id: string;
  project_id: string;
  created_at: string;
}

export function useProjectMetrics(projectId: string) {
  return useQuery({
    queryKey: ['metrics', projectId],
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
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
    },
  });
}

export function useUpdateEVMData(projectId: string, existingMetrics: Metrics | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (evmData: EVMData): Promise<Metrics> => {
      const today = new Date().toISOString().split('T')[0];
      const metrics: MetricsCreate = {
        period_start: existingMetrics?.period_start ?? today,
        period_end: today,
        evm_data: evmData,
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
      };
      const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
    },
  });
}

export function useUpdateMilestones(projectId: string, existingMetrics: Metrics | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (milestones: Milestone[]): Promise<Metrics> => {
      const today = new Date().toISOString().split('T')[0];
      const metrics: MetricsCreate = {
        period_start: existingMetrics?.period_start ?? today,
        period_end: today,
        evm_data: existingMetrics?.evm_data,
        milestones: milestones,
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
      };
      const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
    },
  });
}

export function useUpdateGovernance(projectId: string, existingMetrics: Metrics | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (governanceExceptions: number): Promise<Metrics> => {
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
        governance_exceptions: governanceExceptions,
        sev1_incident: existingMetrics?.sev1_incident ?? false,
      };
      const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
    },
  });
}

interface PMSatisfactionInput {
  delivery_complaints: 'yes' | 'no' | '-';
  design_complaints: 'yes' | 'no' | '-';
  overall_estimation?: number;
}

export function useUpdatePMSatisfaction(projectId: string, existingMetrics: Metrics | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (pmSatisfaction: PMSatisfactionInput): Promise<Metrics> => {
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
        pm_satisfaction: pmSatisfaction,
        client_survey: existingMetrics?.client_survey,
        strategic_impact: existingMetrics?.strategic_impact,
        governance_exceptions: existingMetrics?.governance_exceptions,
        sev1_incident: existingMetrics?.sev1_incident ?? false,
      };
      const response = await api.post<Metrics>(`/metrics/project/${projectId}`, metrics);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics', projectId] });
      queryClient.invalidateQueries({ queryKey: ['scores', projectId] });
    },
  });
}
