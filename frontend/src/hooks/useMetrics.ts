import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { MetricsCreate } from '../types';

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
        const response = await api.get<Metrics>(`/metrics/project/${projectId}/latest`);
        return response.data;
      } catch {
        return null;
      }
    },
    enabled: !!projectId,
  });
}
