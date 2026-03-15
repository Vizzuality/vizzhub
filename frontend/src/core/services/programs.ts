import type { ProgramSummary } from '@/types';
import api from './client';

export const programsApi = {
  list: async (): Promise<ProgramSummary[]> => {
    const response = await api.get<ProgramSummary[]>('/programs');
    return response.data;
  },
  create: async (name: string): Promise<ProgramSummary> => {
    const response = await api.post<ProgramSummary>('/programs', { name });
    return response.data;
  },
};
