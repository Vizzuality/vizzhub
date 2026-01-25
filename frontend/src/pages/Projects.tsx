import { useState, useMemo } from 'react';
import { Plus, LayoutGrid, List, ArrowUp, ArrowDown, ArrowUpDown, Search, X } from 'lucide-react';
import { useQueries } from '@tanstack/react-query';
import { useProjects, useCreateProject } from '../hooks/useProjects';
import { scoresApi } from '../services/api';
import ProjectCard from '../components/Dashboard/ProjectCard';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate, ProjectStatus } from '../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

type ViewMode = 'list' | 'grid';
type SortField = 'name' | 'created_at' | 'status' | 'score';
type SortOrder = 'asc' | 'desc';
type StatusFilter = 'all' | ProjectStatus;

export default function Projects(): JSX.Element {
  const [showForm, setShowForm] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    return (localStorage.getItem('projectsViewMode') as ViewMode) || 'list';
  });
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const [searchName, setSearchName] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [startDateFrom, setStartDateFrom] = useState('');
  const [startDateTo, setStartDateTo] = useState('');

  const { data: projects, isLoading, error } = useProjects();

  const scoreQueries = useQueries({
    queries: (projects ?? []).map((project) => ({
      queryKey: ['scores', project.id],
      queryFn: () => scoresApi.getProjectScores(project.id),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
  });

  const scoresMap = useMemo(() => {
    const map: Record<string, number | null> = {};
    (projects ?? []).forEach((project, index) => {
      const query = scoreQueries[index];
      map[project.id] = query?.data?.scores?.score ?? null;
    });
    return map;
  }, [projects, scoreQueries]);

  const handleViewModeChange = (mode: ViewMode): void => {
    setViewMode(mode);
    localStorage.setItem('projectsViewMode', mode);
  };

  const handleSort = (field: SortField): void => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder(field === 'name' ? 'asc' : 'desc');
    }
  };

  const filteredAndSortedProjects = useMemo(() => {
    if (!projects) return [];

    const filtered = projects.filter((project) => {
      if (searchName && !project.name.toLowerCase().includes(searchName.toLowerCase())) {
        return false;
      }

      if (statusFilter !== 'all' && project.status !== statusFilter) {
        return false;
      }

      if (startDateFrom && project.start_date) {
        if (new Date(project.start_date) < new Date(startDateFrom)) {
          return false;
        }
      }

      if (startDateTo && project.start_date) {
        if (new Date(project.start_date) > new Date(startDateTo)) {
          return false;
        }
      }

      if ((startDateFrom || startDateTo) && !project.start_date) {
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
  }, [projects, sortField, sortOrder, scoresMap, searchName, statusFilter, startDateFrom, startDateTo]);

  const hasActiveFilters = searchName || statusFilter !== 'all' || startDateFrom || startDateTo;

  const clearFilters = (): void => {
    setSearchName('');
    setStatusFilter('all');
    setStartDateFrom('');
    setStartDateTo('');
  };

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
        {isActive ? (
          sortOrder === 'asc' ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />
        ) : (
          <ArrowUpDown className="w-3.5 h-3.5 opacity-50" />
        )}
      </button>
    );
  };
  const createProject = useCreateProject();

  const handleCreate = async (data: ProjectCreate): Promise<void> => {
    await createProject.mutateAsync(data);
    setShowForm(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
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
                value={searchName}
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
                    onClick={() => setStatusFilter(option.value)}
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
      {filteredAndSortedProjects.length > 0 ? (
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
      ) : hasActiveFilters ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground mb-4">No projects match your filters</p>
            <Button variant="outline" onClick={clearFilters}>
              Clear filters
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground mb-4">No projects yet</p>
            <Button onClick={() => setShowForm(true)}>
              Create your first project
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
