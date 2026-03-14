import { Link } from 'react-router-dom';
import {
  BarChart3,
  Github,
  Calendar,
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
  score?: number | null;
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

function ScoreDisplay({ score }: { score?: number | null }): JSX.Element | null {
  if (score === null || score === undefined) return null;
  const color = score >= 70 ? 'text-green-600 dark:text-green-400'
    : score >= 40 ? 'text-yellow-600 dark:text-yellow-400'
    : 'text-red-600 dark:text-red-400';
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Score</span>
      <span className={cn('text-sm font-bold', color)}>{Math.round(score)}</span>
    </div>
  );
}

export default function ProjectCard({
  project,
  viewMode = 'list',
  isAdmin = false,
  score,
}: ProjectCardProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  if (viewMode === 'grid') {
    return (
      <Card className="hover:shadow-lg transition-shadow h-full">
        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base font-semibold line-clamp-2">
              {project.name}
            </CardTitle>
            <StatusBadge status={project.status} />
          </div>

          <div className="flex items-center gap-3">
            <ScoreDisplay score={score} />
          </div>

          <div className="space-y-1 text-sm text-muted-foreground">
            {project.program_name && (
              <span className="flex items-center gap-1.5">
                <Folder className="w-3.5 h-3.5" />
                {project.program_name}
              </span>
            )}
            {project.jira_project_key && (
              <span className="flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5" />
                {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-1.5">
                <Github className="w-3.5 h-3.5" />
                {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5" />
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 pt-2 border-t text-sm">
            {project.has_scorecard && (
              <Link
                to={`/scorecard/${project.id}`}
                className="font-medium text-primary hover:underline"
              >
                Scorecard
              </Link>
            )}
            {isAdmin && (
              <Link
                to={`/projects/${project.id}/edit`}
                className="flex items-center gap-1 font-medium text-muted-foreground hover:text-foreground"
              >
                <Pencil className="w-3 h-3" />
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4">
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-base font-semibold truncate">
              {project.name}
            </CardTitle>
            <StatusBadge status={project.status} />
          </div>
          <div className="flex items-center gap-3 flex-wrap text-sm text-muted-foreground">
            {project.program_name && (
              <span className="flex items-center gap-1.5">
                <Folder className="w-3.5 h-3.5 shrink-0" />
                {project.program_name}
              </span>
            )}
            {project.jira_project_key && (
              <span className="flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5 shrink-0" />
                {project.jira_project_key}
              </span>
            )}
            {project.github_repo && (
              <span className="flex items-center gap-1.5">
                <Github className="w-3.5 h-3.5 shrink-0" />
                {project.github_repo}
              </span>
            )}
            {hasDateRange && (
              <span className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                {project.start_date && formatDate(project.start_date)}
                {project.start_date && project.end_date && ' - '}
                {project.end_date && formatDate(project.end_date)}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <ScoreDisplay score={score} />
          {project.has_scorecard && (
            <Link
              to={`/scorecard/${project.id}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Scorecard
            </Link>
          )}
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
