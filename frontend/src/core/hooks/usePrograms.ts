import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { programsApi } from '@/core/services/programs';

export const usePrograms = () =>
  useQuery({
    queryKey: queryKeys.programs.list,
    queryFn: programsApi.list,
    staleTime: 5 * 60 * 1000,
  });

export const useCreateProgram = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => programsApi.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.programs.all });
    },
  });
};
