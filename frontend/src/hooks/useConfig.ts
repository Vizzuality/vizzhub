import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { ConfigParameter, ConfigParameterUpdate, ValidationResponse } from '../types/config';
import { queryKeys } from '@/core/hooks/queryKeys';

export function useConfigParameters() {
  return useQuery<Record<string, ConfigParameter[]>>({
    queryKey: queryKeys.config.parameters,
    queryFn: async () => {
      const response = await api.get('/config/parameters');
      return response.data;
    },
  });
}

export function useConfigValidation() {
  return useQuery<ValidationResponse>({
    queryKey: queryKeys.config.validation,
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
      const response = await api.patch('/config/parameters', updates);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.config.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.scores.all });
    },
  });
}

export interface ScoreThresholds {
  green: number;
  yellow: number;
}

export function useScoreThresholds(): ScoreThresholds {
  const { data: config } = useConfigParameters();

  const getConstant = (name: string, defaultValue: number): number => {
    const constants = config?.['Gates & Constants'];
    if (!constants) return defaultValue;
    const param = constants.find((p) => p.name === name);
    return param ? Number.parseFloat(param.value) : defaultValue;
  };

  return {
    green: getConstant('const_threshold_green', 80),
    yellow: getConstant('const_threshold_yellow', 60),
  };
}
