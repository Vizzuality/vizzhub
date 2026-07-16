import {
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  ChevronLeft,
  ChevronRight,
  Columns3,
  FoldHorizontal,
  Search,
  UnfoldHorizontal,
  X,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import {
  STATIC_COLUMNS,
  type AccrualSort,
  type SortDir,
  type StaticColumn,
} from '@/modules/accrual/components/AccrualGridColumns';

export interface AccrualFilters {
  year_from: number;
  year_to: number;
  issues_only: boolean;
  search: string;
}

// Fields offered by the toolbar's sort selector. Header-click sorting can set
// other keys (code, value_eur) — the selector then shows no field checked.
const SORT_FIELDS: readonly { key: string; label: string }[] = [
  { key: 'created_at', label: 'Creation date' },
  { key: 'name', label: 'Line' },
  { key: 'window_start', label: 'Start date' },
];

interface AccrualToolbarProps {
  readonly filters: AccrualFilters;
  readonly onChange: (filters: AccrualFilters) => void;
  readonly minYear?: number;
  readonly maxYear?: number;
  readonly columns?: readonly StaticColumn[];
  readonly hiddenColumns?: ReadonlySet<string>;
  readonly onToggleColumn?: (id: string) => void;
  readonly collapsed?: boolean;
  readonly onToggleCollapsed?: () => void;
  readonly sort?: AccrualSort | null;
  readonly onSortChange?: (sort: AccrualSort) => void;
}

function SortSelector({
  sort,
  onSortChange,
}: {
  readonly sort: AccrualSort | null;
  readonly onSortChange: (sort: AccrualSort) => void;
}): JSX.Element {
  const activeField = SORT_FIELDS.find((f) => f.key === sort?.key);
  const dir: SortDir = sort?.dir ?? 'asc';
  const DirIcon = dir === 'asc' ? ArrowUpNarrowWide : ArrowDownWideNarrow;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label="Sort lines">
          <DirIcon className="mr-1 h-4 w-4" />
          {activeField?.label ?? 'Sort'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Sort by</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={activeField?.key ?? ''}
          onValueChange={(key) => onSortChange({ key, dir })}
        >
          {SORT_FIELDS.map((f) => (
            <DropdownMenuRadioItem key={f.key} value={f.key}>
              {f.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={dir}
          onValueChange={(d) =>
            onSortChange({ key: sort?.key ?? SORT_FIELDS[0].key, dir: d as SortDir })
          }
        >
          <DropdownMenuRadioItem value="asc">Ascending</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="desc">Descending</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AccrualToolbar({
  filters,
  onChange,
  minYear,
  maxYear,
  columns = STATIC_COLUMNS,
  hiddenColumns,
  onToggleColumn,
  collapsed = false,
  onToggleCollapsed,
  sort,
  onSortChange,
}: AccrualToolbarProps): JSX.Element {
  const { year_from, year_to, search } = filters;

  const yearLabel = year_from === year_to ? `${year_from}` : `${year_from} – ${year_to}`;
  const hasBounds = minYear !== undefined && maxYear !== undefined;
  const canGoPrev = !hasBounds || year_from > minYear;
  const canGoNext = !hasBounds || year_to < maxYear;
  const searchValue = search ?? '';

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1">
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
      </div>

      <div className="flex items-center gap-2 border-l pl-3">
        <Checkbox
          id="issues_only"
          checked={filters.issues_only}
          onCheckedChange={(v) => onChange({ ...filters, issues_only: v === true })}
        />
        <Label htmlFor="issues_only" className="cursor-pointer text-sm">
          Issues only
        </Label>
      </div>

      <div className="relative ml-auto w-56">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={searchValue}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Filter by project or code…"
          aria-label="Filter by project name or code"
          className="h-9 pl-8 pr-8"
        />
        {searchValue && (
          <button
            type="button"
            aria-label="Clear filter"
            onClick={() => onChange({ ...filters, search: '' })}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {onSortChange && <SortSelector sort={sort ?? null} onSortChange={onSortChange} />}

      {onToggleCollapsed && (
        <Button
          variant={collapsed ? 'default' : 'outline'}
          size="sm"
          aria-label={collapsed ? 'Expand fixed columns' : 'Collapse fixed columns'}
          aria-pressed={collapsed}
          title={
            collapsed
              ? 'Show the selected fixed columns'
              : 'Collapse to the Line column only (more room for months)'
          }
          onClick={onToggleCollapsed}
        >
          {collapsed ? (
            <UnfoldHorizontal className="mr-1 h-4 w-4" />
          ) : (
            <FoldHorizontal className="mr-1 h-4 w-4" />
          )}
          {collapsed ? 'Expand' : 'Collapse'}
        </Button>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" disabled={collapsed}>
            <Columns3 className="mr-1 h-4 w-4" />
            Columns
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Visible columns</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {columns.map((col) => (
            <DropdownMenuCheckboxItem
              key={col.id}
              checked={!hiddenColumns?.has(col.id)}
              onCheckedChange={() => onToggleColumn?.(col.id)}
              onSelect={(e) => e.preventDefault()}
            >
              {col.label}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
