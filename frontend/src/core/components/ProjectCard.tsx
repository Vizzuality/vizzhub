import { Link } from 'react-router-dom';
import {
  BarChart3,
  Github,
  Calendar,
  DollarSign,
  Folder,
  Pencil,
} from 'lucide-react';
import type { Project } from '@/core/types/project';
import { formatDate } from '@/utils/formatters';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/lib/utils';

interface ProjectCardProps {
  project: Project;
  viewMode?: 'list' | 'grid';
  isAdmin?: boolean;
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'proposal': return 'Proposal';
    case 'live': return 'Live';
    case 'finished': return 'Finished';
    default: return status;
  }
}

function getStatusBadgeClasses(status: string): string {
  switch (status) {
    case 'proposal':
      return 'bg-amber-100 text-amber-800 hover:bg-amber-100/80 dark:bg-amber-900 dark:text-amber-200';
    case 'live':
      return '';
    case 'finished':
      return 'bg-green-100 text-green-800 hover:bg-green-100/80 dark:bg-green-900 dark:text-green-200';
    default:
      return '';
  }
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'outline' {
  switch (status) {
    case 'proposal': return 'outline';
    case 'live': return 'secondary';
    case 'finished': return 'default';
    default: return 'secondary';
  }
}

function StatusBadge({ status }: { status: string }): JSX.Element {
  return (
    <Badge
      variant={getStatusVariant(status)}
      className={cn('shrink-0', getStatusBadgeClasses(status))}
    >
      {getStatusLabel(status)}
    </Badge>
  );
}

export default function ProjectCard({
  project,
  viewMode = 'list',
  isAdmin = false,
}: ProjectCardProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  if (viewMode === 'grid') {
    return (
      <Card className="hover:shadow-lg transition-shadow h-full">
        <div className="p-5 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg font-semibold line-clamp-2">
              {project.name}
            </CardTitle>
            <StatusBadge status={project.status} />
          </div>

          <div className="flex items-center gap-2">
            {project.code && (
              <span className="text-sm font-mono text-muted-foreground">
                {project.code}
              </span>
            )}
            {project.is_billable && (
              <Badge variant="outline" className="text-xs gap-1">
                <DollarSign className="w-3 h-3" />
                Billable
              </Badge>
            )}
          </div>

          <div className="space-y-1.5 text-sm text-muted-foreground">
            {project.program_name && (
              <span className="flex items-center gap-2">
                <Folder className="w-4 h-4" />
                {project.program_name}
              </span>
            )}
            {project.jira_project_key && (
              <span className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-2">
                <Github className="w-4 h-4" />
                {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 pt-2 border-t">
            <Link
              to={`/scorecard/${project.id}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Scorecard
            </Link>
            {isAdmin && (
              <Link
                to={`/projects/${project.id}/edit`}
                className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                <Pencil className="w-3.5 h-3.5" />
                Edit
              </Link>
            )}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <CardTitle className="text-xl font-semibold">{project.name}</CardTitle>
            <StatusBadge status={project.status} />
            {project.code && (
              <span className="text-sm font-mono text-muted-foreground">
                {project.code}
              </span>
            )}
            {project.is_billable && (
              <Badge variant="outline" className="text-xs gap-1">
                <DollarSign className="w-3 h-3" />
                Billable
              </Badge>
            )}
          </div>
          <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 text-base text-muted-foreground">
            {project.program_name && (
              <span className="flex items-center gap-2">
                <Folder className="w-5 h-5" />
                {project.program_name}
              </span>
            )}
            {project.jira_project_key && (
              <span className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Jira: {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-2">
                <Github className="w-5 h-5" />
                GitHub: {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 md:flex-shrink-0">
          <Link
            to={`/scorecard/${project.id}`}
            className="text-base font-medium text-primary hover:underline"
          >
            Scorecard
          </Link>
          {isAdmin && (
            <Link
              to={`/projects/${project.id}/edit`}
              className="flex items-center gap-1.5 text-base font-medium text-muted-foreground hover:text-foreground"
            >
              <Pencil className="w-4 h-4" />
              Edit
            </Link>
          )}
        </div>
      </div>
    </Card>
  );
}
