import { useMemo, useState } from 'react';
import { X, File, Search } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Label } from '@/shared/components/ui/label';
import { useMetadataSearch, useTextSearch } from '../hooks/useIsoDocMetadata';
import { STATUS_LABELS } from '../types/isoDocs';
import type { MetadataFilterParams, MetadataSearchResult } from '../types/isoDocs';

interface MetadataFiltersProps {
  readonly filters: MetadataFilterParams;
  readonly onFiltersChange: (filters: MetadataFilterParams) => void;
  readonly onSelect: (nodeId: string) => void;
  readonly onClose: () => void;
}

function collectDistinctValues(results: MetadataSearchResult[]): {
  cats: Set<string>; stats: Set<string>; stds: Set<string>; cls: Set<string>;
} {
  const cats = new Set<string>();
  const stats = new Set<string>();
  const stds = new Set<string>();
  const cls = new Set<string>();

  for (const r of results) {
    if (r.category) cats.add(r.category);
    if (r.status) stats.add(r.status);
    r.standard?.forEach((s) => stds.add(s));
    r.clauses?.forEach((c) => cls.add(c));
  }

  return { cats, stats, stds, cls };
}

function useFilterOptions(allResults: MetadataSearchResult[] | undefined): {
  categories: { value: string; label: string }[];
  statuses: { value: string; label: string }[];
  standards: string[];
  clauses: string[];
} {
  return useMemo(() => {
    if (!allResults) return { categories: [], statuses: [], standards: [], clauses: [] };

    const { cats, stats, stds, cls } = collectDistinctValues(allResults);

    return {
      categories: [...cats]
        .map((v) => ({ value: v, label: v }))
        .sort((a, b) => a.label.localeCompare(b.label)),
      statuses: [...stats]
        .map((v) => ({ value: v, label: STATUS_LABELS[v] ?? v }))
        .sort((a, b) => a.label.localeCompare(b.label)),
      standards: [...stds].sort((a, b) => a.localeCompare(b)),
      clauses: [...cls].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
    };
  }, [allResults]);
}

export function MetadataFilters({
  filters,
  onFiltersChange,
  onSelect,
  onClose,
}: MetadataFiltersProps): JSX.Element {
  const [searchQuery, setSearchQuery] = useState('');
  const { data: allResults } = useMetadataSearch({});
  const hasFilters = !!(filters.category || filters.status || filters.standard || filters.clause);
  const { data: filteredResults } = useMetadataSearch(hasFilters ? filters : {});
  const { data: textResults, isFetching: isSearching } = useTextSearch(searchQuery);
  const options = useFilterOptions(allResults);

  const isTextSearch = searchQuery.length >= 2;
  const metadataResults = hasFilters ? filteredResults : allResults;
  const activeCount = [filters.category, filters.status, filters.standard, filters.clause]
    .filter(Boolean).length;

  const setFilter = (key: keyof MetadataFilterParams, value: string): void => {
    onFiltersChange({
      ...filters,
      [key]: value === '_all' ? undefined : value,
    });
  };

  const clearAll = (): void => {
    onFiltersChange({});
    setSearchQuery('');
  };

  const resultCount = textResults?.length ?? 0;
  const searchStatusText = isSearching
    ? 'Searching...'
    : `${resultCount} ${resultCount === 1 ? 'result' : 'results'}`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="text-xs font-semibold">
          Search & Filter
          {(activeCount > 0 || isTextSearch) && (
            <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] w-4 h-4">
              {activeCount + (isTextSearch ? 1 : 0)}
            </span>
          )}
        </span>
        <div className="flex items-center gap-1">
          {(activeCount > 0 || isTextSearch) && (
            <Button variant="ghost" size="sm" className="h-6 text-xs px-1.5" onClick={clearAll}>
              Clear
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="px-3 py-2 space-y-2.5 border-b">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search in documents..."
            className="h-7 text-xs pl-7"
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Category</Label>
          <Select value={filters.category ?? '_all'} onValueChange={(v) => setFilter('category', v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All categories</SelectItem>
              {options.categories.map((c) => (
                <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select value={filters.status ?? '_all'} onValueChange={(v) => setFilter('status', v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All statuses</SelectItem>
              {options.statuses.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Standard</Label>
          <Select value={filters.standard ?? '_all'} onValueChange={(v) => setFilter('standard', v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All standards</SelectItem>
              {options.standards.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Clause</Label>
          <Select value={filters.clause ?? '_all'} onValueChange={(v) => setFilter('clause', v)}>
            <SelectTrigger className="h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All clauses</SelectItem>
              {options.clauses.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isTextSearch ? (
          <>
            <div className="px-3 py-1.5 text-xs text-muted-foreground">
              {searchStatusText}
            </div>
            <div className="px-1 pb-2">
              {textResults?.map((r) => (
                <button
                  key={r.node_id}
                  className="flex items-start gap-2 w-full text-left px-2 py-1.5 rounded text-sm hover:bg-muted"
                  onClick={() => onSelect(r.node_id)}
                >
                  <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{r.title}</div>
                    <p className="text-xs text-muted-foreground line-clamp-2">{r.snippet}</p>
                  </div>
                </button>
              ))}
              {textResults?.length === 0 && !isSearching && (
                <p className="text-xs text-muted-foreground px-2 py-2">No documents match</p>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="px-3 py-1.5 text-xs text-muted-foreground">
              {metadataResults?.length ?? 0} {metadataResults?.length === 1 ? 'result' : 'results'}
            </div>
            <div className="px-1 pb-2">
              {metadataResults?.map((r) => (
                <button
                  key={r.node_id}
                  className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded text-sm hover:bg-muted"
                  onClick={() => onSelect(r.node_id)}
                >
                  <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{r.title}</div>
                    {r.code && (
                      <span className="text-xs font-mono text-muted-foreground">{r.code}</span>
                    )}
                  </div>
                </button>
              ))}
              {metadataResults?.length === 0 && (
                <p className="text-xs text-muted-foreground px-2 py-2">No documents match</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
