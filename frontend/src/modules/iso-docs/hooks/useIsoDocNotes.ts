import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocNotesApi } from '../services/notes';
import type { NoteCreate, NoteUpdate } from '../types/notes';

const NOTES_ROOT = ['iso-docs', 'notes'] as const;

export function useNodeNotes(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.notesByNode(nodeId ?? ''),
    queryFn: () => isoDocNotesApi.list(nodeId!),
    enabled: !!nodeId,
    refetchOnWindowFocus: false,
  });
}

export function useAllNotes(includeDone: boolean) {
  return useQuery({
    queryKey: queryKeys.isoDocs.allNotes(includeDone),
    queryFn: () => isoDocNotesApi.listAll(includeDone),
    refetchOnWindowFocus: false,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>): void {
  qc.invalidateQueries({ queryKey: NOTES_ROOT });
}

export function useCreateNote(nodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NoteCreate) => isoDocNotesApi.create(nodeId, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: NoteUpdate }) =>
      isoDocNotesApi.update(id, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => isoDocNotesApi.remove(id),
    onSuccess: () => invalidateAll(qc),
  });
}
