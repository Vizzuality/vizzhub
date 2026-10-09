import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';
import type { EventStatsParams } from '../types/events';

export function useEventStats(params: EventStatsParams) {
  return useQuery({
    queryKey: queryKeys.events.stats({ ...params }),
    queryFn: () => eventsApi.stats(params),
  });
}
