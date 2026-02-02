import { useState, useMemo } from 'react';
import { Plus, LayoutGrid, List, ArrowUp, ArrowDown, ArrowUpDown, Search, X } from 'lucide-react';
import { useProjects, useCreateProject } from '../hooks/useProjects';
import { useProjectFilters, type StatusFilter } from '../hooks/useProjectFilters';
import { useProjectSort, type SortField } from '../hooks/useProjectSort';
import { useProjectScoresMap } from '../hooks/useProjectScoresMap';
import ProjectCard from '../components/Dashboard/ProjectCard';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

type ViewMode = 'list' | 'grid';
type SortOrder = 'asc' | 'desc';

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
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    return (localStorage.getItem('projectsViewMode') as ViewMode) || 'list';
  });

  const { data: projects, isLoading, error } = useProjects();
  const {
    filters,
    setSearchName,
    setStatusFilter,
    setStartDateFrom,
    setStartDateTo,
    hasActiveFilters,
    clearFilters,
  } = useProjectFilters();
  const { sortField, sortOrder, handleSort } = useProjectSort();
  const { scoresMap } = useProjectScoresMap(projects);
  const createProject = useCreateProject();

  const handleViewModeChange = (mode: ViewMode): void => {
    setViewMode(mode);
    localStorage.setItem('projectsViewMode', mode);
  };

  const filteredAndSortedProjects = useMemo(() => {
    if (!projects) return [];

    const filtered = projects.filter((project) => {
      if (filters.searchName && !project.name.toLowerCase().includes(filters.searchName.toLowerCase())) {
        return false;
      }

      if (filters.statusFilter !== 'all' && project.status !== filters.statusFilter) {
        return false;
      }

      if (filters.startDateFrom && project.start_date) {
        if (new Date(project.start_date) < new Date(filters.startDateFrom)) {
          return false;
        }
      }

      if (filters.startDateTo && project.start_date) {
        if (new Date(project.start_date) > new Date(filters.startDateTo)) {
          return false;
        }
      }

      if ((filters.startDateFrom || filters.startDateTo) && !project.start_date) {
        return false;
      }

      return true;
    });

    return filtered.sort((a, b) => {
      let comparison = 0;
      if (sortField === 'name') {
        comparison = a.name.localeCompare(b.name);
      } else if (sortField === 'created_at') {
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      } else if (sortField === 'status') {
        comparison = a.status.localeCompare(b.status);
      } else if (sortField === 'score') {
        const scoreA = scoresMap[a.id] ?? -1;
        const scoreB = scoresMap[b.id] ?? -1;
        comparison = scoreA - scoreB;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [projects, sortField, sortOrder, scoresMap, filters]);

  const SortButton = ({ field, label }: { field: SortField; label: string }): JSX.Element => {
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

  const renderProjectsContent = (): JSX.Element => {
    if (filteredAndSortedProjects.length > 0) {
      return (
        <div className={cn(
          "grid gap-4",
          viewMode === 'grid' && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
        )}>
          {filteredAndSortedProjects.map((project) => (
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

  if (isLoading) {
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
        <div className="flex items-center gap-2">
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

      {/* Search and Filters */}
      {projects && projects.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row gap-3">
            {/* Name Search */}
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by name..."
                value={filters.searchName}
                onChange={(e) => setSearchName(e.target.value)}
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
                      filters.statusFilter === option.value ? "bg-muted font-medium" : "hover:bg-muted/50"
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
                value={filters.startDateFrom}
                onChange={(e) => setStartDateFrom(e.target.value)}
                className="w-36"
                placeholder="From"
              />
              <span className="text-muted-foreground">-</span>
              <Input
                type="date"
                value={filters.startDateTo}
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
          </div>

          {/* Results count */}
          {hasActiveFilters && (
            <p className="text-sm text-muted-foreground">
              Showing {filteredAndSortedProjects.length} of {projects.length} projects
            </p>
          )}
        </div>
      )}

      {/* Sort Controls */}
      {projects && projects.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Sort by:</span>
          <SortButton field="name" label="Name" />
          <SortButton field="created_at" label="Created" />
          <SortButton field="status" label="Status" />
          <SortButton field="score" label="Score" />
        </div>
      )}

      {/* Projects List */}
      {renderProjectsContent()}
    </div>
  );
}
