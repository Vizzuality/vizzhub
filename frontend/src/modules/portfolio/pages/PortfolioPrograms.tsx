import { useEffect, useState } from 'react';
import { LayoutGrid, List, Search, X } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useProgramIndex } from '../hooks/usePrograms';
import { useTaxonomies } from '../hooks/useTaxonomies';
import { useClientOptions } from '../hooks/useClientOptions';
import { ProgramCard } from '../components/ProgramCard';
import { ProgramListRow } from '../components/ProgramListRow';
import { UnassignedTray } from '../components/UnassignedTray';
import { CreateProgramDialog } from '../components/CreateProgramDialog';

type ViewMode = 'grid' | 'list';
const SEARCH_DEBOUNCE_MS = 300;

export default function PortfolioPrograms(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const [schema] = useState(() => ({
    view: { defaultValue: (localStorage.getItem('portfolioViewMode') as ViewMode) || 'grid' },
    search: { defaultValue: '' },
    terms: { defaultValue: '' }, // comma-joined term ids
    client: { defaultValue: '' },
  }));
  const { state, setState } = useUrlState(schema);
  const viewMode = state.view as ViewMode;
  const termIds = state.terms ? state.terms.split(',') : [];

  const { data, isLoading } = useProgramIndex({
    search: state.search || undefined,
    term_ids: termIds.length ? termIds : undefined,
    client_id: state.client || undefined,
  });
  const { data: taxonomies } = useTaxonomies();
  const { data: clients } = useClientOptions();

  const [localSearch, setLocalSearch] = useState(state.search);
  useEffect(() => {
    setLocalSearch(state.search);
  }, [state.search]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== state.search) setState({ search: localSearch });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, state.search, setState]);

  const setViewMode = (mode: ViewMode): void => {
    setState({ view: mode });
    localStorage.setItem('portfolioViewMode', mode);
  };

  const toggleTerm = (id: string): void => {
    const next = termIds.includes(id) ? termIds.filter((t) => t !== id) : [...termIds, id];
    setState({ terms: next.join(',') });
  };

  const hasFilters = Boolean(state.search || termIds.length || state.client);

  if (isLoading) return <LoadingSpinner />;
  const programs = data?.programs ?? [];
  const unassigned = data?.unassigned_projects ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            placeholder="Search programs…"
            className="w-56 pl-8"
          />
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm">
              Tags{termIds.length > 0 ? ` (${termIds.length})` : ''}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="max-h-96 w-64 overflow-y-auto">
            {(taxonomies ?? []).map((tax) => (
              <div key={tax.id} className="mb-3 last:mb-0">
                <p className="mb-1 text-xs font-medium text-muted-foreground">{tax.name}</p>
                {tax.terms.filter((t) => t.is_active).map((term) => (
                  <label key={term.id} className="flex items-center gap-2 py-0.5 text-sm">
                    <Checkbox
                      checked={termIds.includes(term.id)}
                      onCheckedChange={() => toggleTerm(term.id)}
                    />
                    {term.name}
                  </label>
                ))}
              </div>
            ))}
          </PopoverContent>
        </Popover>
        <Select
          value={state.client || 'all'}
          onValueChange={(v) => setState({ client: v === 'all' ? '' : v })}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Client" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All clients</SelectItem>
            {(clients ?? []).map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setLocalSearch('');
              setState({ search: '', terms: '', client: '' });
            }}
          >
            <X className="mr-1 h-3.5 w-3.5" />
            Clear
          </Button>
        )}
        <div className="ml-auto flex items-center gap-1">
          {canManage && <CreateProgramDialog />}
          <Button
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
            size="icon"
            title="Grid view"
            onClick={() => setViewMode('grid')}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'secondary' : 'ghost'}
            size="icon"
            title="List view"
            onClick={() => setViewMode('list')}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {programs.length === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No programs match the current filters.
        </p>
      )}

      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {programs.map((p) => (
            <ProgramCard key={p.id} program={p} />
          ))}
        </div>
      ) : (
        <Card>
          {programs.map((p) => (
            <ProgramListRow key={p.id} program={p} />
          ))}
        </Card>
      )}

      <UnassignedTray projects={unassigned} canManage={canManage} />
    </div>
  );
}
