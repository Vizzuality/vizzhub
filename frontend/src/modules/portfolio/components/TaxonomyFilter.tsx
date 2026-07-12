import { ChevronsUpDown } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import type { Taxonomy } from '../types/portfolio';

/** One compact multi-select filter button per taxonomy (index filter bar). */
export function TaxonomyFilter({
  taxonomy,
  selectedIds,
  onToggle,
}: {
  readonly taxonomy: Taxonomy;
  readonly selectedIds: string[];
  readonly onToggle: (termId: string) => void;
}): JSX.Element {
  const active = taxonomy.terms.filter((t) => t.is_active);
  const count = active.filter((t) => selectedIds.includes(t.id)).length;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          {taxonomy.name}
          {count > 0 ? ` (${count})` : ''}
          <ChevronsUpDown className="ml-1 h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="max-h-80 w-56 overflow-y-auto">
        {active.map((term) => (
          <div key={term.id} className="flex items-center gap-2 py-0.5 text-sm">
            <Checkbox
              id={`filter-term-${term.id}`}
              checked={selectedIds.includes(term.id)}
              onCheckedChange={() => onToggle(term.id)}
            />
            <label htmlFor={`filter-term-${term.id}`}>{term.name}</label>
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}
