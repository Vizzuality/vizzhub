import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import type { ProgramProfile, ProgramProfileUpdate } from '../types/portfolio';

type NarrativeKey =
  | 'objective'
  | 'short_description'
  | 'web_copy'
  | 'impact_story'
  | 'main_partner';

const FIELDS: { key: NarrativeKey; label: string; multiline: boolean }[] = [
  { key: 'objective', label: 'Objective', multiline: true },
  { key: 'short_description', label: 'Short description', multiline: true },
  { key: 'web_copy', label: 'Web copy', multiline: true },
  { key: 'impact_story', label: 'Impact story', multiline: true },
  { key: 'main_partner', label: 'Main partner', multiline: false },
];

export function ProgramNarrative({
  profile,
  canManage,
  isSaving,
  onSave,
}: {
  readonly profile: ProgramProfile | null;
  readonly canManage: boolean;
  readonly isSaving: boolean;
  readonly onSave: (diff: ProgramProfileUpdate) => Promise<void>;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});

  const value = (key: NarrativeKey): string => profile?.[key] ?? '';

  const startEdit = (): void => {
    setDraft(Object.fromEntries(FIELDS.map((f) => [f.key, value(f.key)])));
    setEditing(true);
  };

  const save = async (): Promise<void> => {
    const diff: ProgramProfileUpdate = {};
    for (const f of FIELDS) {
      if (draft[f.key] !== value(f.key)) {
        (diff as Record<string, string | null>)[f.key] = draft[f.key].trim() || null;
      }
    }
    if (Object.keys(diff).length > 0) await onSave(diff);
    setEditing(false);
  };

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Narrative</h2>
        {canManage && !editing && (
          <Button variant="outline" size="sm" onClick={startEdit}>
            Edit
          </Button>
        )}
        {editing && (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => void save()} disabled={isSaving}>
              Save
            </Button>
          </div>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key} className="space-y-1">
            <Label className="text-xs text-muted-foreground">{f.label}</Label>
            {editing ? (
              f.multiline ? (
                <Textarea
                  value={draft[f.key]}
                  onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                  rows={3}
                />
              ) : (
                <Input
                  value={draft[f.key]}
                  onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                />
              )
            ) : (
              <p className="whitespace-pre-wrap text-sm">
                {value(f.key) || <span className="text-muted-foreground">—</span>}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
