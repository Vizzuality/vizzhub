import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, LayoutGrid, List } from 'lucide-react';
import { cn } from '@/lib/utils';
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
import { EventCard } from '../components/EventCard';
import { EventForm } from '../components/EventForm';
import { EventsTable } from '../components/EventsTable';
import { useEvents } from '../hooks/useEvents';
import { useEventOptions } from '../hooks/useEventOptions';
import { ALL_SENTINEL, buildYearOptions } from '../utils/constants';
import type { EventListParams } from '../types/events';

const SEARCH_DEBOUNCE_MS = 300;

const SORT_OPTIONS = [
  { value: 'start_date:desc', label: 'Newest first' },
  { value: 'start_date:asc', label: 'Oldest first' },
  { value: 'name:asc', label: 'Name A-Z' },
  { value: 'name:desc', label: 'Name Z-A' },
  { value: 'total_cost:desc', label: 'Highest cost' },
  { value: 'total_cost:asc', label: 'Lowest cost' },
  { value: 'rating:desc', label: 'Highest rating' },
  { value: 'rating:asc', label: 'Lowest rating' },
] as const;

const urlSchema = {
  search: { defaultValue: '' },
  year: { defaultValue: '' },
  theme: { defaultValue: '' },
  type: { defaultValue: '' },
  region: { defaultValue: '' },
  sort: { defaultValue: 'start_date:desc' },
  view: { defaultValue: 'grid' },
};

export default function Events(): JSX.Element {
  const navigate = useNavigate();
  const canManage = usePermission(Action.EVENTS_MANAGE);
  const { state, setState } = useUrlState(urlSchema);
  const { data: options } = useEventOptions();

  const [localSearch, setLocalSearch] = useState(state.search);
  const [creating, setCreating] = useState(false);

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

  const yearOptions = useMemo(() => buildYearOptions(), []);

  const [sortBy, sortDir] = state.sort.split(':');

  const queryParams: EventListParams = {
    ...(state.search && { search: state.search }),
    ...(state.year && { year: Number(state.year) }),
    ...(state.theme && { theme_primary: state.theme }),
    ...(state.type && { event_type: state.type }),
    ...(state.region && { region_focus: state.region }),
    sort_by: sortBy,
    sort_dir: sortDir,
    page_size: 100,
  };

  const { data, isLoading, error } = useEvents(queryParams);
  const events = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasActiveFilters = !!(
    state.search || state.year || state.theme || state.type || state.region
  );

  const handleSelectChange = (
    key: keyof typeof urlSchema,
    value: string,
  ): void => {
    setState({ [key]: value === ALL_SENTINEL ? '' : value });
  };

  if (isLoading && !data) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading events: {error.message}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Events</h1>
        {canManage && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="w-4 h-4 mr-1.5" />
            New Event
          </Button>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search events..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select
          value={state.year || ALL_SENTINEL}
          onValueChange={(v) => handleSelectChange('year', v)}
        >
          <SelectTrigger className="w-[130px] h-9 text-sm">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All Years</SelectItem>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={y}>{y}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={state.theme || ALL_SENTINEL}
          onValueChange={(v) => handleSelectChange('theme', v)}
        >
          <SelectTrigger className="w-[200px] h-9 text-sm">
            <SelectValue placeholder="Theme" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All Themes</SelectItem>
            {(options?.themes ?? []).map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={state.type || ALL_SENTINEL}
          onValueChange={(v) => handleSelectChange('type', v)}
        >
          <SelectTrigger className="w-[180px] h-9 text-sm">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All Types</SelectItem>
            {(options?.event_types ?? []).map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={state.region || ALL_SENTINEL}
          onValueChange={(v) => handleSelectChange('region', v)}
        >
          <SelectTrigger className="w-[220px] h-9 text-sm">
            <SelectValue placeholder="Region" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>All Regions</SelectItem>
            {(options?.regions ?? []).map((r) => (
              <SelectItem key={r} value={r}>{r}</SelectItem>
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

        <div className="flex items-center rounded-md border">
          <button
            type="button"
            aria-label="Grid view"
            className={cn(
              'h-9 px-2.5 flex items-center gap-1',
              state.view === 'grid' ? 'bg-muted' : 'hover:bg-muted/50',
            )}
            onClick={() => setState({ view: 'grid' })}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="List view"
            className={cn(
              'h-9 px-2.5 flex items-center gap-1 border-l',
              state.view === 'list' ? 'bg-muted' : 'hover:bg-muted/50',
            )}
            onClick={() => setState({ view: 'list' })}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Count display */}
      {total > 0 && (
        <p className="text-sm text-muted-foreground">
          Showing {events.length} of {total} events
        </p>
      )}

      {/* Card grid / list view */}
      {events.length > 0 ? (
        state.view === 'list' ? (
          <EventsTable
            events={events}
            onRowClick={(id) => navigate(`/events/${id}`)}
            sortKey={sortBy}
            sortDir={sortDir as 'asc' | 'desc'}
            onSortChange={(k, d) => setState({ sort: `${k}:${d}` })}
          />
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {events.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        )
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground">
              {hasActiveFilters
                ? 'No events match your filters'
                : 'No events yet'}
            </p>
            {canManage && !hasActiveFilters && (
              <Button className="mt-4" onClick={() => setCreating(true)}>
                Create your first event
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {canManage && creating && (
        <EventForm eventId="new" onClose={() => setCreating(false)} />
      )}
    </div>
  );
}
