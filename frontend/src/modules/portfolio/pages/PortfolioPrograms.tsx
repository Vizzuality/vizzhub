import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, LayoutGrid, List, Search, X } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useProgramIndex, useUnassignedProjects, useStageOptions } from '../hooks/usePrograms';
import { useTaxonomies } from '../hooks/useTaxonomies';
import { ProgramCard } from '../components/ProgramCard';
import { ProgramListRow } from '../components/ProgramListRow';
import { UnassignedTray } from '../components/UnassignedTray';
import { CreateProgramDialog } from '../components/CreateProgramDialog';
import { TaxonomyFilter } from '../components/TaxonomyFilter';
import { ClientCombobox } from '../components/ClientCombobox';

type ViewMode = 'grid' | 'list';
const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE = 24;

export default function PortfolioPrograms(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const [schema] = useState(() => ({
    view: { defaultValue: (localStorage.getItem('portfolioViewMode') as ViewMode) || 'grid' },
    search: { defaultValue: '' },
    terms: { defaultValue: '' }, // comma-joined term ids
    client: { defaultValue: '' },
    stage: { defaultValue: '' },
    page: { defaultValue: 1 },
  }));
  const { state, setState } = useUrlState(schema);
  const viewMode = state.view as ViewMode;
  const termIds = state.terms ? state.terms.split(',') : [];

  const { data, isLoading } = useProgramIndex({
    search: state.search || undefined,
    term_ids: termIds.length ? termIds : undefined,
    client_id: state.client || undefined,
    stage: state.stage || undefined,
    page: state.page,
    n: PAGE_SIZE,
  });
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const { data: taxonomies } = useTaxonomies();
  const { data: stages } = useStageOptions();

  const [localSearch, setLocalSearch] = useState(state.search);
  useEffect(() => {
    setLocalSearch(state.search);
  }, [state.search]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== state.search) setState({ search: localSearch, page: 1 });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, state.search, setState]);

  const setViewMode = (mode: ViewMode): void => {
    setState({ view: mode });
    localStorage.setItem('portfolioViewMode', mode);
  };

  const toggleTerm = (id: string): void => {
    const next = termIds.includes(id) ? termIds.filter((t) => t !== id) : [...termIds, id];
    setState({ terms: next.join(','), page: 1 });
  };

  const hasFilters = Boolean(state.search || termIds.length || state.client || state.stage);

  const { data: unassignedData } = useUnassignedProjects();

  if (isLoading) return <LoadingSpinner />;
  const programs = data?.programs ?? [];
  const unassigned = unassignedData ?? [];

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
        {(taxonomies ?? [])
          .filter((t) => t.is_active)
          .map((tax) => (
            <TaxonomyFilter
              key={tax.id}
              taxonomy={tax}
              selectedIds={termIds}
              onToggle={toggleTerm}
            />
          ))}
        <Select
          value={state.stage || 'all'}
          onValueChange={(v) => setState({ stage: v === 'all' ? '' : v, page: 1 })}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Stage" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {(stages ?? []).map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <ClientCombobox value={state.client} onChange={(v) => setState({ client: v, page: 1 })} />
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setLocalSearch('');
              setState({ search: '', terms: '', client: '', stage: '', page: 1 });
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

      {total > 0 && (
        <div className="flex flex-col items-center justify-between gap-2 pt-2 sm:flex-row">
          <p className="text-sm text-muted-foreground">
            Showing {programs.length} of {total} programs
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setState({ page: state.page - 1 })}
              disabled={state.page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {state.page} of {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setState({ page: state.page + 1 })}
              disabled={state.page >= pages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <UnassignedTray projects={unassigned} canManage={canManage} />
    </div>
  );
}
