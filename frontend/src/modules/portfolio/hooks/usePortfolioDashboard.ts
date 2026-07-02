import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '@/modules/portfolio/services/portfolio';
import type { ClientLeaderboard, ProjectLeaderboard } from '@/modules/portfolio/types/portfolio';

export function useProjectLeaderboard(year?: number): UseQueryResult<ProjectLeaderboard> {
  return useQuery<ProjectLeaderboard>({
    queryKey: queryKeys.portfolio.dashboard.projects({ year: year ?? null }),
    queryFn: () => portfolioApi.dashboard.projects(year),
  });
}

export function useClientLeaderboard(year?: number): UseQueryResult<ClientLeaderboard> {
  return useQuery<ClientLeaderboard>({
    queryKey: queryKeys.portfolio.dashboard.clients({ year: year ?? null }),
    queryFn: () => portfolioApi.dashboard.clients(year),
  });
}
