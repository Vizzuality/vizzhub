import type { MetricsCreate, ScoreResponse, ScoringConfig } from '../types';
import api from '@/core/services/client';

interface BatchScoresResponse {
  scores: Record<string, ScoreResponse>;
  errors: Record<string, string>;
}

export const scoresApi = {
  getProjectScores: async (
    projectId: string,
    year?: number,
    month?: number,
  ): Promise<ScoreResponse> => {
    const params: Record<string, number> = {};
    if (year !== undefined) params.year = year;
    if (month !== undefined) params.month = month;

    const response = await api.get<ScoreResponse>(
      `/scores/project/${projectId}`,
      { params },
    );
    return response.data;
  },

  getBatchScores: async (
    projectIds: string[],
    snapshotType = 'cumulative',
  ): Promise<BatchScoresResponse> => {
    const response = await api.post<BatchScoresResponse>('/scores/batch', {
      project_ids: projectIds,
      snapshot_type: snapshotType,
    });
    return response.data;
  },

  getScoreHistory: async (
    projectId: string,
    limit = 10,
  ): Promise<ScoreResponse[]> => {
    const response = await api.get<ScoreResponse[]>(
      `/scores/project/${projectId}/history`,
      { params: { limit } },
    );
    return response.data;
  },

  calculate: async (
    metrics: MetricsCreate,
    sev1Incident = false,
  ): Promise<ScoreResponse> => {
    const response = await api.post<ScoreResponse>('/scores/calculate', {
      metrics,
      sev1_incident: sev1Incident,
    });
    return response.data;
  },
};

export const configApi = {
  get: async (): Promise<ScoringConfig> => {
    const response = await api.get<ScoringConfig>('/config');
    return response.data;
  },

  validate: async (): Promise<{ valid: boolean; groups: Record<string, boolean>; errors?: string[] }> => {
    const response = await api.get<{ valid: boolean; groups: Record<string, boolean>; errors?: string[] }>(
      '/config/validate',
    );
    return response.data;
  },

  updateParameters: async (updates: Array<{ name: string; value: string }>): Promise<void> => {
    await api.patch('/config/parameters', { updates });
  },
};
