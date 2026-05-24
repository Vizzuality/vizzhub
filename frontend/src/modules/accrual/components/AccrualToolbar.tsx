import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Label } from '@/shared/components/ui/label';

export interface AccrualFilters {
  year_from: number;
  year_to: number;
  issues_only: boolean;
}

interface AccrualToolbarProps {
  readonly filters: AccrualFilters;
  readonly onChange: (filters: AccrualFilters) => void;
  readonly minYear?: number;
  readonly maxYear?: number;
}

export function AccrualToolbar({
  filters,
  onChange,
  minYear,
  maxYear,
}: AccrualToolbarProps): JSX.Element {
  const { year_from, year_to } = filters;

  const yearLabel = year_from === year_to ? `${year_from}` : `${year_from} – ${year_to}`;
  const hasBounds = minYear !== undefined && maxYear !== undefined;
  const canGoPrev = !hasBounds || year_from > minYear;
  const canGoNext = !hasBounds || year_to < maxYear;

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon"
        aria-label="previous year"
        disabled={!canGoPrev}
        onClick={() => onChange({ ...filters, year_from: year_from - 1, year_to: year_to - 1 })}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <span className="min-w-[5rem] text-center text-sm font-medium tabular-nums">
        {yearLabel}
      </span>

      <Button
        variant="outline"
        size="icon"
        aria-label="next year"
        disabled={!canGoNext}
        onClick={() => onChange({ ...filters, year_from: year_from + 1, year_to: year_to + 1 })}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>

      <div className="flex items-center gap-2 pl-2 border-l ml-1">
        <Checkbox
          id="issues_only"
          checked={filters.issues_only}
          onCheckedChange={(v) => onChange({ ...filters, issues_only: v === true })}
        />
        <Label htmlFor="issues_only" className="text-sm cursor-pointer">
          Issues only
        </Label>
      </div>
    </div>
  );
}
