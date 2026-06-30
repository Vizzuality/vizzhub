import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { portfolioApi } from '../services/portfolio';

export function useTaxonomies() {
  return useQuery({
    queryKey: queryKeys.portfolio.taxonomies,
    queryFn: () => portfolioApi.listTaxonomies(),
  });
}
