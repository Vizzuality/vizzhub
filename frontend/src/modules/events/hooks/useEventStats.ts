import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEventStats(year?: number) {
  return useQuery({
    queryKey: queryKeys.events.stats(year),
    queryFn: () => eventsApi.stats(year),
  });
}
