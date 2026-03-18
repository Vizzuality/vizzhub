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
import { StatusBadge } from '@/shared/components/StatusBadge';
import { cn } from '@/lib/utils';


interface ProjectCardProps {
  readonly project: Project;
  readonly viewMode?: 'list' | 'grid';
  readonly isAdmin?: boolean;
  readonly score?: number | null;
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'text-green-600 dark:text-green-400';
  if (score >= 40) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function ScoreDisplay({ score }: Readonly<{ score?: number | null }>): JSX.Element | null {
  if (score === null || score === undefined) return null;
  const color = getScoreColor(score);
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Score</span>
      <span className={cn('text-sm font-bold', color)}>{Math.round(score)}</span>
    </div>
  );
}

function ProjectMetadata({ project }: { project: Project }): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;
  return (
    <>
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
    </>
  );
}

function ProjectLinks({ project, isAdmin }: { project: Project; isAdmin: boolean }): JSX.Element {
  return (
    <>
      {project.has_scorecard && (
        <Link
          to={`/scorecard/${project.id}`}
          className="text-sm font-medium text-primary hover:underline"
        >
          Scorecard
        </Link>
      )}
      <Link
        to={`/tracker/projects/${project.id}`}
        className="text-sm font-medium text-primary hover:underline"
      >
        Tracker
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
    </>
  );
}

export default function ProjectCard({
  project,
  viewMode = 'list',
  isAdmin = false,
  score,
}: ProjectCardProps): JSX.Element {
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
            <ProjectMetadata project={project} />
          </div>

          <div className="flex items-center gap-3 pt-2 border-t text-sm">
            <ProjectLinks project={project} isAdmin={isAdmin} />
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
            <ProjectMetadata project={project} />
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <ScoreDisplay score={score} />
          <ProjectLinks project={project} isAdmin={isAdmin} />
        </div>
      </div>
    </Card>
  );
}
