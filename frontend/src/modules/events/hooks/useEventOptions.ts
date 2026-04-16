import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEventOptions() {
  return useQuery({
    queryKey: queryKeys.events.options,
    queryFn: eventsApi.options,
    staleTime: Infinity,
  });
}
