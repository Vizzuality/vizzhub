import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { ConfigParameter, ConfigParameterUpdate, ValidationResponse } from '../types/config';

export function useConfigParameters() {
  return useQuery<Record<string, ConfigParameter[]>>({
    queryKey: ['config', 'parameters'],
    queryFn: async () => {
      const response = await api.get('/config/parameters');
      return response.data;
    },
  });
}

export function useConfigValidation() {
  return useQuery<ValidationResponse>({
    queryKey: ['config', 'validation'],
    queryFn: async () => {
      const response = await api.get('/config/validate');
      return response.data;
    },
  });
}

export function useUpdateConfigParameters() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (updates: ConfigParameterUpdate[]) => {
      const response = await api.put('/config/parameters', updates);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['scores'] });
    },
  });
}
