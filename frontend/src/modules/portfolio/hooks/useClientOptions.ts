import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '@/modules/portfolio/services/portfolio';
import type { ClientOption } from '@/modules/portfolio/types/portfolio';

export function useClientOptions(): UseQueryResult<ClientOption[]> {
  return useQuery<ClientOption[]>({
    queryKey: queryKeys.portfolio.clients.options(),
    queryFn: () => portfolioApi.listClientOptions(),
    staleTime: 5 * 60 * 1000,
  });
}
