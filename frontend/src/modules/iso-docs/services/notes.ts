import api from '@/core/services/client';
import type { IsoDocNote, AdminIsoDocNote, NoteCreate, NoteUpdate } from '../types/notes';

export const isoDocNotesApi = {
  list: async (nodeId: string): Promise<IsoDocNote[]> => {
    const { data } = await api.get<IsoDocNote[]>(`/iso-docs/nodes/${nodeId}/notes`);
    return data;
  },

  create: async (nodeId: string, body: NoteCreate): Promise<IsoDocNote> => {
    const { data } = await api.post<IsoDocNote>(`/iso-docs/nodes/${nodeId}/notes`, body);
    return data;
  },

  update: async (noteId: string, body: NoteUpdate): Promise<IsoDocNote> => {
    const { data } = await api.patch<IsoDocNote>(`/iso-docs/notes/${noteId}`, body);
    return data;
  },

  remove: async (noteId: string): Promise<void> => {
    await api.delete(`/iso-docs/notes/${noteId}`);
  },

  listAll: async (includeDone: boolean): Promise<AdminIsoDocNote[]> => {
    const { data } = await api.get<AdminIsoDocNote[]>(
      '/iso-docs/notes',
      { params: { include_done: includeDone } },
    );
    return data;
  },
};
