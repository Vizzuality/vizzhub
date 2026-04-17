import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, Search } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { EntryCard } from '../components/EntryCard';
import { EntryForm } from '../components/EntryForm';
import { useDevstackEntries, useRefreshShas } from '../hooks/useDevstack';
import { ENTRY_TYPES } from '../types/devstack';

const ALL_SENTINEL = '__all__';
const SEARCH_DEBOUNCE_MS = 300;

const SORT_OPTIONS = [
  { value: 'name:asc', label: 'Name A-Z' },
  { value: 'name:desc', label: 'Name Z-A' },
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc', label: 'Oldest first' },
  { value: 'type:asc', label: 'Type A-Z' },
] as const;

const urlSchema = {
  search: { defaultValue: '' },
  type: { defaultValue: '' },
  sort: { defaultValue: 'name:asc' },
};

export default function Catalog(): JSX.Element {
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const navigate = useNavigate();
  const { state, setState } = useUrlState(urlSchema);
  const refreshShas = useRefreshShas();

  const [localSearch, setLocalSearch] = useState(state.search);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setLocalSearch(state.search);
  }, [state.search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== state.search) {
        setState({ search: localSearch });
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, state.search, setState]);

  const [sortBy, sortDir] = state.sort.split(':');

  const params = {
    ...(state.search && { search: state.search }),
    ...(state.type && { type: state.type }),
    sort_by: sortBy,
    sort_dir: sortDir,
    page_size: 100,
  };

  const { data, isLoading, error } = useDevstackEntries(params);
  const entries = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasActiveFilters = !!(state.search || state.type);

  const handleCardClick = (id: string): void => {
    navigate(`/devstack/${id}`);
  };

  if (isLoading && !data) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading catalog: {error.message}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">DevStack Catalog</h1>
        {canManage && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refreshShas.mutate()}
              disabled={refreshShas.isPending}
            >
              <RefreshCw
                className={`w-4 h-4 mr-1.5 ${refreshShas.isPending ? 'animate-spin' : ''}`}
              />
              Refresh SHAs
            </Button>
            <Button size="sm" onClick={() => setSelectedId('new')}>
              <Plus className="w-4 h-4 mr-1.5" />
              Add Entry
            </Button>
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search entries..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select
          value={state.type || ALL_SENTINEL}
          onValueChange={(v) => setState({ type: v === ALL_SENTINEL ? '' : v })}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All types</SelectItem>
            {ENTRY_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={state.sort}
          onValueChange={(v) => setState({ sort: v })}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Count display */}
      {total > 0 && (
        <p className="text-sm text-muted-foreground">
          Showing {entries.length} of {total} entries
        </p>
      )}

      {/* Card grid */}
      {entries.length > 0 ? (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((entry) => (
            <EntryCard
              key={entry.id}
              entry={entry}
              onClick={handleCardClick}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground">
              {hasActiveFilters
                ? 'No entries match your filters'
                : 'No catalog entries yet'}
            </p>
            {canManage && !hasActiveFilters && (
              <Button
                className="mt-4"
                onClick={() => setSelectedId('new')}
              >
                Add your first entry
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {selectedId !== null && (
        <EntryForm
          selectedId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
