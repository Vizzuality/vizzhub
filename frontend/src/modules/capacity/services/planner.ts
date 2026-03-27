import api from '@/core/services/client';
import type {
  CellUpdate,
  PlannerResponse,
  UpdatedAtResponse,
} from '@/modules/capacity/types/planner';

export const plannerApi = {
  get: async (
    start: string,
    end: string,
    groupBy: string,
  ): Promise<PlannerResponse> => {
    const response = await api.get<PlannerResponse>('/capacity/planner', {
      params: { start, end, group_by: groupBy },
    });
    return response.data;
  },

  updateCells: async (updates: CellUpdate[]): Promise<{ updated: number }> => {
    const response = await api.patch<{ updated: number }>(
      '/capacity/planner/cells',
      { updates },
    );
    return response.data;
  },

  deleteRow: async (
    projectId: string,
    userId: string,
  ): Promise<{ deleted: number }> => {
    const response = await api.delete<{ deleted: number }>(
      `/capacity/planner/rows/${projectId}/${userId}`,
    );
    return response.data;
  },

  getUpdatedAt: async (
    start: string,
    end: string,
  ): Promise<UpdatedAtResponse> => {
    const response = await api.get<UpdatedAtResponse>(
      '/capacity/planner/updated-at',
      { params: { start, end } },
    );
    return response.data;
  },
};
