import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEvent(id: string) {
  return useQuery({
    queryKey: queryKeys.events.detail(id),
    queryFn: () => eventsApi.get(id),
    enabled: !!id,
  });
}

export function useAddAttendees() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      eventId,
      attendees,
    }: {
      eventId: string;
      attendees: { user_id: string; role: string }[];
    }) => eventsApi.addAttendees(eventId, attendees),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(variables.eventId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}

export function useRemoveAttendee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, userId }: { eventId: string; userId: string }) =>
      eventsApi.removeAttendee(eventId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(variables.eventId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}
