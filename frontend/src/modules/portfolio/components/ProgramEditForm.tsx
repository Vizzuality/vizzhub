import { useState } from 'react';
import { Star } from 'lucide-react';
import { getApiErrorMessage } from '@/utils/apiErrors';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  useRenameProgram,
  useReplaceProgramTerms,
  useUpdateProgramProfile,
} from '../hooks/usePrograms';
import { useTaxonomies } from '../hooks/useTaxonomies';
import {
  PROFILE_TEXT_FIELDS,
  TAXONOMY_CHIP_CLASSES,
  TAXONOMY_CHIP_FALLBACK,
  type ProfileTextKey,
} from '../utils/programs';
import type {
  ProgramProfileUpdate,
  ProgramSummary,
  Taxonomy,
} from '../types/portfolio';

interface TermsDraft {
  selected: string[];
  primary: string | null;
}

function draftFor(program: ProgramSummary, taxonomyId: string): TermsDraft {
  const chips = program.terms.filter((t) => t.taxonomy_id === taxonomyId);
  return {
    selected: chips.map((c) => c.term_id),
    primary: chips.find((c) => c.is_primary)?.term_id ?? null,
  };
}

function TermToggleChip({
  name,
  slug,
  selected,
  isPrimary,
  allowsPrimary,
  onClick,
}: {
  readonly name: string;
  readonly slug: string;
  readonly selected: boolean;
  readonly isPrimary: boolean;
  readonly allowsPrimary: boolean;
  readonly onClick: () => void;
}): JSX.Element {
  const title = allowsPrimary && selected && !isPrimary ? 'Click again to set as primary' : undefined;
  return (
    <button
      type="button"
      aria-pressed={selected}
      title={title}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition-colors',
        selected
          ? cn(TAXONOMY_CHIP_CLASSES[slug] ?? TAXONOMY_CHIP_FALLBACK, 'bg-accent/60')
          : 'border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground',
      )}
    >
      {isPrimary && <Star className="h-3 w-3 fill-amber-400 text-amber-400" />}
      {name}
    </button>
  );
}

/**
 * Single edit form for the whole program: name, tags per taxonomy, narrative fields.
 * Tag chips toggle on click; with allows_primary a second click on a selected chip
 * promotes it to primary, a third deselects it.
 */
export function ProgramEditForm({
  program,
  onDone,
}: {
  readonly program: ProgramSummary;
  readonly onDone: () => void;
}): JSX.Element {
  const { data: taxonomies } = useTaxonomies();
  const active = (taxonomies ?? []).filter((t) => t.is_active);

  const rename = useRenameProgram(program.id);
  const updateProfile = useUpdateProgramProfile(program.id);
  const replaceTerms = useReplaceProgramTerms(program.id);

  const [name, setName] = useState(program.name);
  const [fields, setFields] = useState<Record<ProfileTextKey, string>>(() =>
    Object.fromEntries(
      PROFILE_TEXT_FIELDS.map((f) => [f.key, program.profile?.[f.key] ?? '']),
    ) as Record<ProfileTextKey, string>,
  );
  const [terms, setTerms] = useState<Record<string, TermsDraft>>(() =>
    Object.fromEntries((taxonomies ?? []).map((t) => [t.id, draftFor(program, t.id)])),
  );
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const termsDraft = (tax: Taxonomy): TermsDraft => terms[tax.id] ?? draftFor(program, tax.id);

  const cycleTerm = (tax: Taxonomy, termId: string): void => {
    const draft = termsDraft(tax);
    let next: TermsDraft;
    if (!draft.selected.includes(termId)) {
      next =
        tax.cardinality === 'single'
          ? { selected: [termId], primary: null }
          : { ...draft, selected: [...draft.selected, termId] };
    } else if (tax.allows_primary && draft.primary !== termId) {
      next = { ...draft, primary: termId };
    } else {
      next = {
        selected: draft.selected.filter((t) => t !== termId),
        primary: draft.primary === termId ? null : draft.primary,
      };
    }
    setTerms((d) => ({ ...d, [tax.id]: next }));
  };

  const save = async (): Promise<void> => {
    setError('');
    setSaving(true);
    try {
      const trimmed = name.trim();
      if (trimmed && trimmed !== program.name) await rename.mutateAsync(trimmed);

      const diff: ProgramProfileUpdate = {};
      for (const f of PROFILE_TEXT_FIELDS) {
        if (fields[f.key] !== (program.profile?.[f.key] ?? '')) {
          diff[f.key] = fields[f.key].trim() || null;
        }
      }
      if (Object.keys(diff).length > 0) await updateProfile.mutateAsync(diff);

      for (const tax of active) {
        const draft = termsDraft(tax);
        const before = draftFor(program, tax.id);
        const changed =
          draft.primary !== before.primary
          || draft.selected.length !== before.selected.length
          || draft.selected.some((id) => !before.selected.includes(id));
        if (changed) {
          await replaceTerms.mutateAsync({
            taxonomy_id: tax.id,
            term_ids: draft.selected,
            primary_term_id:
              draft.primary && draft.selected.includes(draft.primary) ? draft.primary : null,
          });
        }
      }
      onDone();
    } catch (err) {
      setError(
        getApiErrorMessage(err as Error, {
          conflict: 'A program with this name already exists',
          badRequest: 'Invalid tag selection',
          fallback: 'Could not save the program',
        }),
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      className="space-y-8"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="max-w-md space-y-1.5">
        <Label htmlFor="program-name" className="text-xs uppercase tracking-wider text-muted-foreground">
          Name
        </Label>
        <Input
          id="program-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Tags</h2>
        <div className="space-y-3">
          {active.map((tax) => {
            const draft = termsDraft(tax);
            return (
              <div key={tax.id} className="flex items-start gap-4">
                <span className="w-36 shrink-0 pt-1 text-xs uppercase tracking-wider text-muted-foreground">
                  {tax.name}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {tax.terms.filter((t) => t.is_active).map((term) => (
                    <TermToggleChip
                      key={term.id}
                      name={term.name}
                      slug={tax.slug}
                      selected={draft.selected.includes(term.id)}
                      isPrimary={draft.primary === term.id}
                      allowsPrimary={tax.allows_primary}
                      onClick={() => cycleTerm(tax, term.id)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">Narrative</h2>
        <div className="grid grid-cols-1 gap-x-10 gap-y-5 md:grid-cols-2">
          {PROFILE_TEXT_FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label
                htmlFor={`profile-${f.key}`}
                className="text-xs uppercase tracking-wider text-muted-foreground"
              >
                {f.label}
              </Label>
              {f.multiline ? (
                <Textarea
                  id={`profile-${f.key}`}
                  value={fields[f.key]}
                  onChange={(e) => setFields((d) => ({ ...d, [f.key]: e.target.value }))}
                  rows={4}
                />
              ) : (
                <Input
                  id={`profile-${f.key}`}
                  value={fields[f.key]}
                  onChange={(e) => setFields((d) => ({ ...d, [f.key]: e.target.value }))}
                  placeholder={f.key === 'website_url' ? 'https://…' : undefined}
                />
              )}
            </div>
          ))}
        </div>
      </section>

      <div className="flex items-center justify-end gap-2">
        {error && <p className="mr-auto text-sm text-destructive">{error}</p>}
        <Button type="button" variant="ghost" onClick={onDone} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving || !name.trim()}>
          Save changes
        </Button>
      </div>
    </form>
  );
}
