import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { rsvpsApi } from '../services/rsvps';
import type {
  EventDetail,
  EventListResponse,
  EventSummary,
  RsvpStatus,
} from '../types/events';

function adjustCounts(
  current: EventSummary['rsvp_counts'],
  oldStatus: RsvpStatus | null,
  newStatus: RsvpStatus | null,
): EventSummary['rsvp_counts'] {
  const next = { ...current };
  if (oldStatus) next[oldStatus] = Math.max(0, next[oldStatus] - 1);
  if (newStatus) next[newStatus] = next[newStatus] + 1;
  return next;
}

export function useSetRsvp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      eventId,
      status,
    }: {
      eventId: string;
      status: RsvpStatus;
    }) => rsvpsApi.set(eventId, status),
    onMutate: async ({ eventId, status }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.events.all });

      const prevDetail = queryClient.getQueryData<EventDetail>(
        queryKeys.events.detail(eventId),
      );
      const prevLists = queryClient.getQueriesData<EventListResponse>({
        queryKey: ['events', 'list'],
      });

      if (prevDetail) {
        queryClient.setQueryData<EventDetail>(
          queryKeys.events.detail(eventId),
          {
            ...prevDetail,
            my_rsvp_status: status,
            rsvp_counts: adjustCounts(
              prevDetail.rsvp_counts,
              prevDetail.my_rsvp_status,
              status,
            ),
          },
        );
      }
      for (const [key, data] of prevLists) {
        if (!data) continue;
        queryClient.setQueryData<EventListResponse>(key, {
          ...data,
          items: data.items.map((evt) =>
            evt.id === eventId
              ? {
                  ...evt,
                  my_rsvp_status: status,
                  rsvp_counts: adjustCounts(
                    evt.rsvp_counts,
                    evt.my_rsvp_status,
                    status,
                  ),
                }
              : evt,
          ),
        });
      }

      return { prevDetail, prevLists };
    },
    onError: (_err, { eventId }, ctx) => {
      if (!ctx) return;
      if (ctx.prevDetail) {
        queryClient.setQueryData(
          queryKeys.events.detail(eventId),
          ctx.prevDetail,
        );
      }
      for (const [key, data] of ctx.prevLists) {
        queryClient.setQueryData(key, data);
      }
    },
    onSettled: (_d, _e, { eventId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(eventId),
      });
    },
  });
}

export function useDeleteRsvp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ eventId }: { eventId: string }) =>
      rsvpsApi.remove(eventId),
    onMutate: async ({ eventId }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.events.all });
      const prevDetail = queryClient.getQueryData<EventDetail>(
        queryKeys.events.detail(eventId),
      );
      const prevLists = queryClient.getQueriesData<EventListResponse>({
        queryKey: ['events', 'list'],
      });

      if (prevDetail) {
        queryClient.setQueryData<EventDetail>(
          queryKeys.events.detail(eventId),
          {
            ...prevDetail,
            my_rsvp_status: null,
            rsvp_counts: adjustCounts(
              prevDetail.rsvp_counts,
              prevDetail.my_rsvp_status,
              null,
            ),
          },
        );
      }
      for (const [key, data] of prevLists) {
        if (!data) continue;
        queryClient.setQueryData<EventListResponse>(key, {
          ...data,
          items: data.items.map((evt) =>
            evt.id === eventId
              ? {
                  ...evt,
                  my_rsvp_status: null,
                  rsvp_counts: adjustCounts(
                    evt.rsvp_counts,
                    evt.my_rsvp_status,
                    null,
                  ),
                }
              : evt,
          ),
        });
      }

      return { prevDetail, prevLists };
    },
    onError: (_err, { eventId }, ctx) => {
      if (!ctx) return;
      if (ctx.prevDetail) {
        queryClient.setQueryData(
          queryKeys.events.detail(eventId),
          ctx.prevDetail,
        );
      }
      for (const [key, data] of ctx.prevLists) {
        queryClient.setQueryData(key, data);
      }
    },
    onSettled: (_d, _e, { eventId }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(eventId),
      });
    },
  });
}
