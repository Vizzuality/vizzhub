import { Badge } from '@/shared/components/ui/badge';
import { TAXONOMY_CHIP_CLASSES, TAXONOMY_CHIP_FALLBACK } from '../utils/programs';
import type { TermChip } from '../types/portfolio';

export function TermChips({
  terms,
  max,
}: {
  readonly terms: TermChip[];
  readonly max?: number;
}): JSX.Element | null {
  if (terms.length === 0) return null;
  const shown = max ? terms.slice(0, max) : terms;
  const overflow = terms.length - shown.length;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((t) => (
        <Badge
          key={t.term_id}
          variant="outline"
          className={TAXONOMY_CHIP_CLASSES[t.taxonomy_slug] ?? TAXONOMY_CHIP_FALLBACK}
        >
          {t.is_primary ? '★ ' : ''}
          {t.name}
        </Badge>
      ))}
      {overflow > 0 && (
        <Badge variant="outline" className={TAXONOMY_CHIP_FALLBACK}>
          +{overflow}
        </Badge>
      )}
    </div>
  );
}
