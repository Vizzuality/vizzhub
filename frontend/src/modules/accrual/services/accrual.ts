import api from '@/core/services/client';
import type {
  AccrualPeriod,
  AccrualPeriodCreate,
  AccrualPeriodUpdate,
} from '@/modules/accrual/types/accrual';

export const accrualApi = {
  periods: {
    list: async (): Promise<AccrualPeriod[]> => {
      const r = await api.get<AccrualPeriod[]>('/accrual/periods');
      return r.data;
    },
    current: async (): Promise<AccrualPeriod | null> => {
      const r = await api.get<AccrualPeriod | null>('/accrual/periods/current');
      return r.data;
    },
    create: async (payload: AccrualPeriodCreate): Promise<AccrualPeriod> => {
      const r = await api.post<AccrualPeriod>('/accrual/periods', payload);
      return r.data;
    },
    patch: async (id: string, payload: AccrualPeriodUpdate): Promise<AccrualPeriod> => {
      const r = await api.patch<AccrualPeriod>(`/accrual/periods/${id}`, payload);
      return r.data;
    },
    seedRates: async (): Promise<Record<string, string>> => {
      const r = await api.get<Record<string, string>>('/accrual/periods/seed-rates');
      return r.data;
    },
  },
};
