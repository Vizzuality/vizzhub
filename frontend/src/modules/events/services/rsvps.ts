import api from '@/core/services/client';
import type { RsvpStatus } from '../types/events';

export const rsvpsApi = {
  set: async (eventId: string, status: RsvpStatus): Promise<void> => {
    await api.put(`/events/${eventId}/rsvp`, { status });
  },
  remove: async (eventId: string): Promise<void> => {
    await api.delete(`/events/${eventId}/rsvp`);
  },
};
