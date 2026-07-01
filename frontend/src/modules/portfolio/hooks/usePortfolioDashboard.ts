import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '../services/portfolio';
import type { PortfolioDashboardSummary } from '../types/portfolio';

export function usePortfolioDashboard(year?: number) {
  return useQuery<PortfolioDashboardSummary>({
    queryKey: queryKeys.portfolio.dashboard.summary({ year: year ?? null }),
    queryFn: () => portfolioApi.dashboard.summary(year),
    staleTime: 60_000,
  });
}
