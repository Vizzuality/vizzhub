import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { programsApi } from '@/core/services/programs';

export const usePrograms = () =>
  useQuery({
    queryKey: queryKeys.programs.list,
    queryFn: programsApi.list,
    staleTime: 5 * 60 * 1000,
  });
