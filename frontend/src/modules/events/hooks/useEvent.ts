import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';
import type { AttendeeUpdate } from '../types/events';

export function useEvent(id: string) {
  return useQuery({
    queryKey: queryKeys.events.detail(id),
    queryFn: () => eventsApi.get(id),
    enabled: !!id,
  });
}

export interface AttendeeBatch {
  toAdd: { user_id: string; role: string; cost: number | null }[];
  toRemove: string[];
  toUpdate: { user_id: string; changes: AttendeeUpdate }[];
}

export function useBatchAttendees() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      eventId,
      batch,
    }: {
      eventId: string;
      batch: AttendeeBatch;
    }) => {
      const tasks: Promise<unknown>[] = [];
      if (batch.toAdd.length) {
        tasks.push(eventsApi.addAttendees(eventId, batch.toAdd));
      }
      for (const uid of batch.toRemove) {
        tasks.push(eventsApi.removeAttendee(eventId, uid));
      }
      for (const { user_id, changes } of batch.toUpdate) {
        tasks.push(eventsApi.updateAttendee(eventId, user_id, changes));
      }
      const results = await Promise.allSettled(tasks);
      const failed = results.filter((r) => r.status === 'rejected');
      return { results, failed };
    },
    onSettled: (_data, _err, { eventId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(eventId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}
