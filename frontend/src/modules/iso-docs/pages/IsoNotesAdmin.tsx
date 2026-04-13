import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Trash2, Check, Pencil } from 'lucide-react';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useAllNotes, useUpdateNote, useDeleteNote } from '../hooks/useIsoDocNotes';
import type { AdminIsoDocNote } from '../types/notes';

const URL_SCHEMA = {
  done: { defaultValue: '0' as string },
};

function NoteRow({ note }: { readonly note: AdminIsoDocNote }): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.content);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const handleSave = (): void => {
    updateNote.mutate(
      { id: note.id, body: { content: draft } },
      { onSuccess: () => setEditing(false) },
    );
  };

  return (
    <div className={`border rounded p-3 space-y-2 ${note.done ? 'opacity-60' : ''}`}>
      {editing ? (
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="min-h-[80px] text-sm"
        />
      ) : (
        <DocViewer content={note.content} emptyMessage="" />
      )}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{note.created_by_name ?? 'Unknown'}</span>
        <span>·</span>
        <span>{new Date(note.created_at).toLocaleDateString('en-GB')}</span>
        <div className="ml-auto flex items-center gap-1">
          {editing ? (
            <>
              <Button size="sm" className="h-7" onClick={handleSave} disabled={updateNote.isPending}>
                Save
              </Button>
              <Button
                size="sm" variant="ghost" className="h-7"
                onClick={() => { setEditing(false); setDraft(note.content); }}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => setEditing(true)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost" size="sm" className="h-7 px-2"
                onClick={() => updateNote.mutate({ id: note.id, body: { done: !note.done } })}
              >
                <Check className={`h-3.5 w-3.5 ${note.done ? 'text-green-600' : ''}`} />
                <span className="ml-1">{note.done ? 'Done' : 'Mark done'}</span>
              </Button>
              <Button
                variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  if (globalThis.confirm('Delete this note?')) deleteNote.mutate(note.id);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function IsoNotesAdmin(): JSX.Element {
  const { state, setState } = useUrlState(URL_SCHEMA);
  const includeDone = state.done === '1';
  const { data: notes = [], isLoading } = useAllNotes(includeDone);

  const grouped = useMemo(() => {
    const map = new Map<string, { title: string; slug: string | null; items: AdminIsoDocNote[] }>();
    for (const note of notes) {
      const entry = map.get(note.node_id) ?? { title: note.node_title, slug: note.node_slug, items: [] };
      entry.items.push(note);
      map.set(note.node_id, entry);
    }
    return Array.from(map.entries()).sort(([, a], [, b]) => a.title.localeCompare(b.title));
  }, [notes]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">ISO Notes</h1>
        <div className="flex items-center gap-2">
          <Switch
            id="show-done"
            checked={includeDone}
            onCheckedChange={(checked: boolean) => setState({ done: checked ? '1' : '0' })}
          />
          <Label htmlFor="show-done" className="text-sm">Show completed</Label>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!isLoading && grouped.length === 0 && (
        <p className="text-sm text-muted-foreground italic">No notes to show.</p>
      )}

      <div className="space-y-6">
        {grouped.map(([nodeId, group]) => {
          const pending = group.items.filter((n) => !n.done).length;
          return (
            <section key={nodeId} className="space-y-2">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold">
                  {group.slug ? (
                    <Link to={`/iso/docs?page=${group.slug}`} className="hover:underline inline-flex items-center gap-1">
                      {group.title}
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  ) : (
                    group.title
                  )}
                </h2>
                <span className="text-xs text-muted-foreground">
                  {pending} pending · {group.items.length} total
                </span>
              </div>
              <div className="space-y-2">
                {group.items.map((note) => <NoteRow key={note.id} note={note} />)}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
