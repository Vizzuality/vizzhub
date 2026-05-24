import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';

export interface AccrualFilters {
  year_from: number;
  year_to: number;
  status: 'proposal' | 'live' | 'finished' | 'all';
  currency: string;
  issues_only: boolean;
}

interface AccrualToolbarProps {
  readonly filters: AccrualFilters;
  readonly onChange: (filters: AccrualFilters) => void;
  readonly currencies: readonly string[];
  readonly minYear?: number;
  readonly maxYear?: number;
}

const STATUS_OPTIONS: { value: AccrualFilters['status']; label: string }[] = [
  { value: 'live', label: 'Live' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'finished', label: 'Finished' },
  { value: 'all', label: 'All' },
];

export function AccrualToolbar({
  filters,
  onChange,
  currencies,
  minYear,
  maxYear,
}: AccrualToolbarProps): JSX.Element {
  const { year_from, year_to, status, currency } = filters;

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

      <Select
        value={status}
        onValueChange={(v) => onChange({ ...filters, status: v as AccrualFilters['status'] })}
      >
        <SelectTrigger className="w-32" aria-label="status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {STATUS_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={currency} onValueChange={(v) => onChange({ ...filters, currency: v })}>
        <SelectTrigger className="w-28" aria-label="currency">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All</SelectItem>
          {currencies.map((c) => (
            <SelectItem key={c} value={c}>
              {c}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

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
