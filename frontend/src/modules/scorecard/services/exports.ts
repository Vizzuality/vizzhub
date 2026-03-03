import api from '@/core/services/client';

export interface ExportParams {
  start: string;
  end: string;
  snapshotType?: string;
}

export const exportsApi = {
  exportProjectDetail: async (
    projectId: string,
    params: ExportParams,
  ): Promise<Blob> => {
    const response = await api.get(`/exports/project/${projectId}`, {
      params: {
        start: params.start,
        end: params.end,
        snapshot_type: params.snapshotType ?? 'cumulative',
      },
      responseType: 'blob',
    });
    return response.data;
  },

  exportGlobalDashboard: async (params: ExportParams): Promise<Blob> => {
    const response = await api.get('/exports/global', {
      params: {
        start: params.start,
        end: params.end,
        snapshot_type: params.snapshotType ?? 'cumulative',
      },
      responseType: 'blob',
    });
    return response.data;
  },
};
