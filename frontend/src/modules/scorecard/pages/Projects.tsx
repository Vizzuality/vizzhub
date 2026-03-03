import { useState, useMemo, useCallback, useEffect } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
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
import { usePaginatedProjects, useCreateProject } from '@/core/hooks/useProjects';
import {
  useProjectListParams,
  type SortField,
  type StatusFilter,
  type SortOrder,
} from '../hooks/useProjectListParams';
import { useProjectScoresMap } from '../hooks/useProjectScoresMap';
import ProjectCard from '../components/Dashboard/ProjectCard';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '@/core/types/project';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { cn } from '@/lib/utils';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

type ViewMode = 'list' | 'grid';

const SEARCH_DEBOUNCE_MS = 300;

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
  const [showForm, setShowForm] = useState(false);
  const [viewModeSchema] = useState(() => ({
    view: { defaultValue: (localStorage.getItem('projectsViewMode') as ViewMode) || 'list' },
  }));
  const { state: viewState, setState: setViewState } = useUrlState(viewModeSchema);
  const viewMode = viewState.view as ViewMode;

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

  const { data, isLoading, error } = usePaginatedProjects(params);
  const projects = data?.items;
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const { scoresMap } = useProjectScoresMap(projects);
  const createProject = useCreateProject();

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
    setViewState({ view: mode });
    localStorage.setItem('projectsViewMode', mode);
  }, [setViewState]);

  const displayedProjects = useMemo(() => {
    if (!projects) return [];
    if (sortField !== 'score') return projects;

    return [...projects].sort((a, b) => {
      const scoreA = scoresMap[a.id] ?? -1;
      const scoreB = scoresMap[b.id] ?? -1;
      const comparison = scoreA - scoreB;
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [projects, sortField, sortOrder, scoresMap]);

  const renderSortButton = (field: SortField, label: string): JSX.Element => {
    const isActive = sortField === field;
    return (
      <button
        onClick={() => handleSort(field)}
        className={cn(
          "flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
          isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
        )}
      >
        {label}
        {getSortIcon(isActive, sortOrder)}
      </button>
    );
  };

  const handleCreate = async (data: ProjectCreate): Promise<void> => {
    await createProject.mutateAsync(data);
    setShowForm(false);
  };

  const renderPagination = (): JSX.Element | null => {
    if (total === 0) return null;

    return (
      <div className="flex items-center justify-between pt-4">
        <p className="text-sm text-muted-foreground">
          Showing {displayedProjects.length} of {total} projects
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
    if (displayedProjects.length > 0) {
      return (
        <div className={cn(
          "grid gap-4",
          viewMode === 'grid' && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
        )}>
          {displayedProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              viewMode={viewMode}
              score={scoresMap[project.id]}
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
          <Button onClick={() => setShowForm(true)}>
            Create your first project
          </Button>
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
    <div className="space-y-6">
      {/* Create Form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Project</CardTitle>
          </CardHeader>
          <CardContent>
            <ProjectForm
              onSubmit={handleCreate}
              onCancel={() => setShowForm(false)}
              isLoading={createProject.isPending}
            />
          </CardContent>
        </Card>
      )}

      {/* Search, Filters & Actions */}
      <div className="space-y-3">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Name Search */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search by name..."
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground whitespace-nowrap">Status:</span>
            <div className="flex items-center border rounded-lg p-1">
              {([
                { value: 'all', label: 'All' },
                { value: 'in_progress', label: 'In Progress' },
                { value: 'finished', label: 'Finished' },
              ] as const).map((option) => (
                <button
                  key={option.value}
                  onClick={() => setStatusFilter(option.value as StatusFilter)}
                  className={cn(
                    "px-3 py-1 text-sm rounded transition-colors",
                    statusFilter === option.value ? "bg-muted font-medium" : "hover:bg-muted/50"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Date Range */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground whitespace-nowrap">Start date:</span>
            <Input
              type="date"
              value={startDateFrom}
              onChange={(e) => setStartDateFrom(e.target.value)}
              className="w-36"
              placeholder="From"
            />
            <span className="text-muted-foreground">-</span>
            <Input
              type="date"
              value={startDateTo}
              onChange={(e) => setStartDateTo(e.target.value)}
              className="w-36"
              placeholder="To"
            />
          </div>

          {/* Clear Filters */}
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="gap-1">
              <X className="w-4 h-4" />
              Clear
            </Button>
          )}

          <div className="flex items-center gap-2 md:ml-auto">
            <div className="flex items-center border rounded-lg p-1">
              <button
                onClick={() => handleViewModeChange('list')}
                className={cn(
                  "p-1.5 rounded transition-colors",
                  viewMode === 'list' ? "bg-muted" : "hover:bg-muted/50"
                )}
                title="List view"
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleViewModeChange('grid')}
                className={cn(
                  "p-1.5 rounded transition-colors",
                  viewMode === 'grid' ? "bg-muted" : "hover:bg-muted/50"
                )}
                title="Grid view"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
            <Button onClick={() => setShowForm(true)}>
              <Plus className="w-5 h-5 mr-2" />
              Create Project
            </Button>
          </div>
        </div>
      </div>

      {/* Sort Controls */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Sort by:</span>
        {renderSortButton('name', 'Name')}
        {renderSortButton('created_at', 'Created')}
        {renderSortButton('status', 'Status')}
        {renderSortButton('score', 'Score')}
      </div>

      {/* Projects List */}
      {renderProjectsContent()}

      {/* Pagination */}
      {renderPagination()}
    </div>
  );
}
