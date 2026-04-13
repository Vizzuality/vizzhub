import { useState } from 'react';
import { Check, Trash2 } from 'lucide-react';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { formatDate } from '@/utils/formatters';
import {
  useNodeNotes,
  useCreateNote,
  useUpdateNote,
  useDeleteNote,
} from '../hooks/useIsoDocNotes';
import type { IsoDocNote } from '../types/notes';

interface NotesPanelProps {
  readonly nodeId: string;
}

function NoteItem({
  note,
  onToggleDone,
  onDelete,
}: {
  readonly note: IsoDocNote;
  readonly onToggleDone: (note: IsoDocNote) => void;
  readonly onDelete: (note: IsoDocNote) => void;
}): JSX.Element {
  return (
    <div className={`border rounded p-3 space-y-2 ${note.done ? 'opacity-60' : ''}`}>
      <DocViewer content={note.content} emptyMessage="" />
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{note.created_by_name ?? 'Unknown'}</span>
        <span>·</span>
        <span>{formatDate(note.created_at)}</span>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => onToggleDone(note)}
          >
            <Check className={`h-3.5 w-3.5 ${note.done ? 'text-green-600' : ''}`} />
            <span className="ml-1">{note.done ? 'Done' : 'Mark done'}</span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(note)}
            aria-label="Delete note"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function NotesPanel({ nodeId }: NotesPanelProps): JSX.Element {
  const [draft, setDraft] = useState('');
  const { data: notes = [], isLoading } = useNodeNotes(nodeId);
  const createNote = useCreateNote(nodeId);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const handleAdd = (): void => {
    const content = draft.trim();
    if (!content) return;
    createNote.mutate({ content }, {
      onSuccess: () => setDraft(''),
    });
  };

  const handleToggle = (note: IsoDocNote): void => {
    updateNote.mutate({ id: note.id, body: { done: !note.done } });
  };

  const handleDelete = (note: IsoDocNote): void => {
    if (!globalThis.confirm('Delete this note?')) return;
    deleteNote.mutate(note.id);
  };

  return (
    <div className="border rounded p-4 space-y-3 bg-muted/30">
      <h3 className="text-sm font-semibold">Notes ({notes.length})</h3>
      {isLoading && <p className="text-xs text-muted-foreground">Loading...</p>}
      {!isLoading && notes.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No notes yet.</p>
      )}
      <div className="space-y-2">
        {notes.map((note) => (
          <NoteItem
            key={note.id}
            note={note}
            onToggleDone={handleToggle}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <div className="space-y-2 pt-2 border-t">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note. Markdown supported."
          className="min-h-[80px] text-sm"
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={handleAdd}
            disabled={!draft.trim() || createNote.isPending}
          >
            {createNote.isPending ? 'Adding...' : 'Add note'}
          </Button>
        </div>
      </div>
    </div>
  );
}
