import api from '@/core/services/client';
import type {
  Attendee,
  AttendeeUpdate,
  EventCreate,
  EventDetail,
  EventListParams,
  EventListResponse,
  EventOptions,
  EventStats,
  EventSummary,
  EventUpdate,
} from '../types/events';

export const eventsApi = {
  list: async (params: EventListParams = {}): Promise<EventListResponse> => {
    const response = await api.get<EventListResponse>('/events', { params });
    return response.data;
  },

  get: async (id: string): Promise<EventDetail> => {
    const response = await api.get<EventDetail>(`/events/${id}`);
    return response.data;
  },

  create: async (data: EventCreate): Promise<EventSummary> => {
    const response = await api.post<EventSummary>('/events', data);
    return response.data;
  },

  update: async (id: string, data: EventUpdate): Promise<EventSummary> => {
    const response = await api.put<EventSummary>(`/events/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/events/${id}`);
  },

  addAttendees: async (
    eventId: string,
    attendees: { user_id: string; role: string; cost?: number | null }[],
  ): Promise<void> => {
    await api.post(`/events/${eventId}/attendees`, attendees);
  },

  updateAttendee: async (
    eventId: string,
    userId: string,
    data: AttendeeUpdate,
  ): Promise<Attendee> => {
    const response = await api.patch<Attendee>(
      `/events/${eventId}/attendees/${userId}`,
      data,
    );
    return response.data;
  },

  removeAttendee: async (eventId: string, userId: string): Promise<void> => {
    await api.delete(`/events/${eventId}/attendees/${userId}`);
  },

  stats: async (year?: number): Promise<EventStats> => {
    const response = await api.get<EventStats>('/events/stats', {
      params: year ? { year } : {},
    });
    return response.data;
  },

  options: async (): Promise<EventOptions> => {
    const response = await api.get<EventOptions>('/events/options');
    return response.data;
  },
};
