import { useState } from 'react';
import { isAxiosError } from 'axios';
import { Star } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { useReplaceProgramTerms } from '../hooks/usePrograms';
import { useTaxonomies } from '../hooks/useTaxonomies';
import { TermChips } from './TermChips';
import type { ProgramSummary, Taxonomy } from '../types/portfolio';

function TaxonomyEditor({
  taxonomy,
  programId,
  assigned,
  assignedPrimary,
}: {
  readonly taxonomy: Taxonomy;
  readonly programId: string;
  readonly assigned: string[];
  readonly assignedPrimary: string | null;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>(assigned);
  const [primary, setPrimary] = useState<string | null>(assignedPrimary);
  const [error, setError] = useState('');
  const replaceTerms = useReplaceProgramTerms(programId);

  const toggle = (termId: string): void => {
    if (taxonomy.cardinality === 'single') {
      setSelected(selected.includes(termId) ? [] : [termId]);
      setPrimary(null);
      return;
    }
    setSelected(
      selected.includes(termId) ? selected.filter((t) => t !== termId) : [...selected, termId],
    );
    if (primary === termId) setPrimary(null);
  };

  const save = async (): Promise<void> => {
    setError('');
    try {
      await replaceTerms.mutateAsync({
        taxonomy_id: taxonomy.id,
        term_ids: selected,
        primary_term_id: primary && selected.includes(primary) ? primary : null,
      });
      setOpen(false);
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 400) {
        setError(String(err.response.data?.detail ?? 'Invalid selection'));
      } else {
        setError('Could not save tags');
      }
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) {
          setSelected(assigned);
          setPrimary(assignedPrimary);
          setError('');
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={`Edit ${taxonomy.name}`}>
          Edit
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 space-y-2">
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {taxonomy.terms.filter((t) => t.is_active).map((term) => (
            <div key={term.id} className="flex items-center gap-2">
              <Checkbox
                id={`term-${term.id}`}
                checked={selected.includes(term.id)}
                onCheckedChange={() => toggle(term.id)}
              />
              <label htmlFor={`term-${term.id}`} className="flex-1 text-sm">
                {term.name}
              </label>
              {taxonomy.allows_primary && selected.includes(term.id) && (
                <button
                  type="button"
                  aria-label={`Set ${term.name} as primary`}
                  onClick={() => setPrimary(primary === term.id ? null : term.id)}
                >
                  <Star
                    className={cn(
                      'h-3.5 w-3.5',
                      primary === term.id
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-muted-foreground',
                    )}
                  />
                </button>
              )}
            </div>
          ))}
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <Button size="sm" onClick={() => void save()} disabled={replaceTerms.isPending}>
          Save
        </Button>
      </PopoverContent>
    </Popover>
  );
}

export function ProgramTagsSection({
  program,
  canManage,
}: {
  readonly program: ProgramSummary;
  readonly canManage: boolean;
}): JSX.Element {
  const { data: taxonomies } = useTaxonomies();
  const active = (taxonomies ?? []).filter((t) => t.is_active);
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium">Tags</h2>
      {active.map((tax) => {
        const chips = program.terms.filter((t) => t.taxonomy_id === tax.id);
        return (
          <div key={tax.id} className="flex items-start gap-3">
            <span className="w-32 shrink-0 pt-0.5 text-xs text-muted-foreground">{tax.name}</span>
            <div className="flex-1">
              <TermChips terms={chips} />
              {chips.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
            </div>
            {canManage && (
              <TaxonomyEditor
                taxonomy={tax}
                programId={program.id}
                assigned={chips.map((c) => c.term_id)}
                assignedPrimary={chips.find((c) => c.is_primary)?.term_id ?? null}
              />
            )}
          </div>
        );
      })}
    </section>
  );
}
