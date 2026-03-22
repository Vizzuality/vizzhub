import api from '@/core/services/client';
import type { PeriodInsight, PeriodUserInsight } from '@/modules/capacity/types/capacity';

export const capacityApi = {
  getInsights: async (startDate: string, endDate: string): Promise<PeriodInsight[]> => {
    const response = await api.get<PeriodInsight[]>('/capacity/insights', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
  getInsightsDetail: async (
    fa: string,
    startDate: string,
    endDate: string,
  ): Promise<PeriodUserInsight[]> => {
    const response = await api.get<PeriodUserInsight[]>('/capacity/insights/detail', {
      params: { fa, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
