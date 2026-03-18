import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  LayoutGrid,
  List,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { usePaginatedAllProjects } from '@/core/hooks/useProjects';
import {
  useProjectListParams,
  type SortField,
  type StatusFilter,
  type SortOrder,
} from '@/core/hooks/useProjectListParams';
import { useProjectScoresMap } from '@/modules/scorecard/hooks/useProjectScoresMap';
import { useProjectCostsMap } from '@/modules/tracker/hooks/useProjectCostsMap';
import ProjectCard from '@/core/components/ProjectCard';
import { useAuth } from '@/core/hooks/useAuth';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Card,
  CardContent,
} from '@/shared/components/ui/card';
import { cn } from '@/lib/utils';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

type ViewMode = 'list' | 'grid';

const SEARCH_DEBOUNCE_MS = 300;
const VIEW_MODE_STORAGE_KEY = 'coreProjectsViewMode';

function getSortIcon(isActive: boolean, sortOrder: SortOrder): JSX.Element {
  if (!isActive) {
    return <ArrowUpDown className="w-3.5 h-3.5 opacity-50" />;
  }
  if (sortOrder === 'asc') {
    return <ArrowUp className="w-3.5 h-3.5" />;
  }
  return <ArrowDown className="w-3.5 h-3.5" />;
}

export default function Projects(): JSX.Element {
  const navigate = useNavigate();
  const { user } = useAuth();
  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const isAdmin = bypassAuth || user?.role === 'admin';

  const [viewMode, setViewMode] = useState<ViewMode>(
    () => (localStorage.getItem(VIEW_MODE_STORAGE_KEY) as ViewMode) || 'list'
  );

  const {
    params,
    page,
    searchName,
    statusFilter,
    startDateFrom,
    startDateTo,
    sortField,
    sortOrder,
    hasActiveFilters,
    setSearchName,
    setStatusFilter,
    setStartDateFrom,
    setStartDateTo,
    setPage,
    handleSort,
    clearFilters,
  } = useProjectListParams();

  const { data, isLoading, error } = usePaginatedAllProjects(params);
  const projects = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const { scoresMap } = useProjectScoresMap(projects);
  const { costsMap } = useProjectCostsMap(projects);

  const [localSearch, setLocalSearch] = useState(searchName);

  useEffect(() => {
    setLocalSearch(searchName);
  }, [searchName]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== searchName) {
        setSearchName(localSearch);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch, searchName, setSearchName]);

  const handleViewModeChange = useCallback((mode: ViewMode): void => {
    setViewMode(mode);
    localStorage.setItem(VIEW_MODE_STORAGE_KEY, mode);
  }, []);

  const renderSortButton = (field: SortField, label: string): JSX.Element => {
    const isActive = sortField === field;
    return (
      <button
        onClick={() => handleSort(field)}
        className={cn(
          'flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
          isActive
            ? 'bg-muted text-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
        )}
      >
        {label}
        {getSortIcon(isActive, sortOrder)}
      </button>
    );
  };

  const renderPagination = (): JSX.Element | null => {
    if (total === 0) return null;

    return (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-4">
        <p className="text-sm text-muted-foreground">
          Showing {projects.length} of {total} projects
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= pages}
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    );
  };

  const renderProjectsContent = (): JSX.Element => {
    if (projects.length > 0) {
      return (
        <div className={cn(
          'grid gap-4',
          viewMode === 'grid'
            ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
            : 'grid-cols-1',
        )}>
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              viewMode={viewMode}
              isAdmin={isAdmin}
              score={scoresMap[project.id]}
              costs={costsMap[project.id]}
            />
          ))}
        </div>
      );
    }

    if (hasActiveFilters) {
      return (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground mb-4">No projects match your filters</p>
            <Button variant="outline" onClick={clearFilters}>
              Clear filters
            </Button>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <p className="text-muted-foreground mb-4">No projects yet</p>
          {isAdmin && (
            <Button onClick={() => navigate('/projects/new')}>
              Create your first project
            </Button>
          )}
        </CardContent>
      </Card>
    );
  };

  if (isLoading && !data) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">Error loading projects: {error.message}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search, Filters & Actions */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by name or code..."
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1">
              {([
                { value: 'all', label: 'All' },
                { value: 'proposal', label: 'Proposal' },
                { value: 'live', label: 'Live' },
                { value: 'finished', label: 'Finished' },
              ] as const).map((option) => (
                <button
                  key={option.value}
                  onClick={() => setStatusFilter(option.value as StatusFilter)}
                  className={cn(
                    'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                    statusFilter === option.value
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>

          </div>

          <div className="flex items-center gap-2 sm:ml-auto">
            <div className="flex items-center border rounded-lg p-0.5">
              <button
                onClick={() => handleViewModeChange('list')}
                className={cn(
                  'p-1.5 rounded transition-colors',
                  viewMode === 'list' ? 'bg-muted' : 'hover:bg-muted/50',
                )}
                title="List view"
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleViewModeChange('grid')}
                className={cn(
                  'p-1.5 rounded transition-colors',
                  viewMode === 'grid' ? 'bg-muted' : 'hover:bg-muted/50',
                )}
                title="Grid view"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
            {isAdmin && (
              <Button size="sm" onClick={() => navigate('/projects/new')}>
                <Plus className="w-4 h-4 mr-1.5" />
                Create Project
              </Button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Start:</span>
            <Input
              type="date"
              value={startDateFrom}
              onChange={(e) => setStartDateFrom(e.target.value)}
              className="w-36 h-8 text-sm"
              min="2018-01-01"
              max="2030-12-31"
            />
            <span className="text-muted-foreground">-</span>
            <Input
              type="date"
              value={startDateTo}
              onChange={(e) => setStartDateTo(e.target.value)}
              className="w-36 h-8 text-sm"
              min="2018-01-01"
              max="2030-12-31"
            />
          </div>

          <div className="flex items-center gap-1 ml-auto">
            <span className="text-sm text-muted-foreground">Sort:</span>
            {renderSortButton('name', 'Name')}
            {renderSortButton('created_at', 'Created')}
            {renderSortButton('status', 'Status')}
          </div>
        </div>
      </div>

      {hasActiveFilters && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/50 text-sm">
          <span className="text-muted-foreground">Filters active</span>
          <Button variant="outline" size="sm" onClick={clearFilters} className="gap-1 h-7 ml-2">
            <X className="w-3.5 h-3.5" />
            Clear all filters
          </Button>
        </div>
      )}

      {renderProjectsContent()}
      {renderPagination()}
    </div>
  );
}
