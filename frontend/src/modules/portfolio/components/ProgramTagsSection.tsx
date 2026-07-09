import { useTaxonomies } from '../hooks/useTaxonomies';
import { TermChips } from './TermChips';
import type { ProgramSummary } from '../types/portfolio';

/** Read-only tag chips grouped by taxonomy; editing lives in ProgramEditForm. */
export function ProgramTagsSection({
  program,
}: {
  readonly program: ProgramSummary;
}): JSX.Element {
  const { data: taxonomies } = useTaxonomies();
  const active = (taxonomies ?? []).filter((t) => t.is_active);
  return (
    <section className="space-y-4">
      <h2 className="text-base font-semibold">Tags</h2>
      <div className="space-y-3">
        {active.map((tax) => {
          const chips = program.terms.filter((t) => t.taxonomy_id === tax.id);
          return (
            <div key={tax.id} className="flex items-start gap-4">
              <span className="w-36 shrink-0 pt-0.5 text-xs uppercase tracking-wider text-muted-foreground">
                {tax.name}
              </span>
              <div className="min-w-0 flex-1">
                <TermChips terms={chips} />
                {chips.length === 0 && <span className="text-sm text-muted-foreground/50">—</span>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
