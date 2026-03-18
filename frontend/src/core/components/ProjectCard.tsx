import { Link } from 'react-router-dom';
import {
  BarChart3,
  Github,
  Calendar,
  Folder,
  Pencil,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import type { Project } from '@/core/types/project';
import type { ProjectCostSummaryLite } from '@/modules/tracker/types/tracker';
import { formatDate } from '@/utils/formatters';
import { formatCurrency } from '@/modules/tracker/utils/constants';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { cn } from '@/lib/utils';


interface ProjectCardProps {
  readonly project: Project;
  readonly viewMode?: 'list' | 'grid';
  readonly isAdmin?: boolean;
  readonly score?: number | null;
  readonly costs?: ProjectCostSummaryLite | null;
}

function getBurnColor(pct: number | null): string {
  if (pct == null) return 'bg-muted-foreground/40';
  if (pct > 100) return 'bg-red-500';
  if (pct >= 80) return 'bg-yellow-500';
  return 'bg-green-500';
}

function Metric({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: string;
  muted?: boolean;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground/70 leading-none mb-0.5">
        {label}
      </div>
      <div
        className={cn(
          'text-xs font-medium leading-tight truncate',
          muted ? 'text-muted-foreground/40' : 'text-foreground',
        )}
      >
        {value}
      </div>
    </div>
  );
}

function ProjectMetrics({
  score,
  costs,
}: {
  score?: number | null;
  costs?: ProjectCostSummaryLite | null;
}): JSX.Element | null {
  if (score == null && !costs) return null;

  return (
    <div className="flex flex-wrap items-end gap-x-4 gap-y-1.5 py-1.5 px-2 rounded bg-muted/40 dark:bg-muted/20">
      {score != null && (
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground/70 leading-none mb-0.5">
            Score
          </div>
          <div
            className={cn(
              'text-xs font-bold leading-tight',
              score >= 70
                ? 'text-green-600 dark:text-green-400'
                : score >= 40
                  ? 'text-yellow-600 dark:text-yellow-400'
                  : 'text-red-600 dark:text-red-400',
            )}
          >
            {Math.round(score)}
          </div>
        </div>
      )}
      {costs && (
        <>
          <Metric
            label="Budget"
            value={costs.budget != null ? formatCurrency(costs.budget) : '—'}
            muted={costs.budget == null}
          />
          <Metric
            label="Costs"
            value={formatCurrency(costs.total_cost)}
          />
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground/70 leading-none mb-0.5">
              Burn
            </div>
            <div className="flex items-center gap-1">
              <span
                className={cn(
                  'inline-block w-1.5 h-1.5 rounded-full shrink-0',
                  getBurnColor(costs.burn_percentage),
                )}
              />
              <span className="text-xs font-medium leading-tight">
                {costs.burn_percentage != null
                  ? `${costs.burn_percentage.toFixed(1)}%`
                  : '—'}
              </span>
            </div>
          </div>
          <Metric label="Progress" value="—" muted />
          <Metric label="Income" value="—" muted />
        </>
      )}
    </div>
  );
}

function ProjectMeta({ project }: { project: Project }): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;
  return (
    <div className="flex items-center gap-3 flex-wrap text-xs text-muted-foreground">
      {project.program_name && (
        <span className="flex items-center gap-1">
          <Folder className="w-3 h-3 shrink-0" />
          {project.program_name}
        </span>
      )}
      {project.jira_project_key && (
        <span className="flex items-center gap-1">
          <BarChart3 className="w-3 h-3 shrink-0" />
          {project.jira_project_key}
        </span>
      )}
      {project.github_repo && (
        <span className="flex items-center gap-1">
          <Github className="w-3 h-3 shrink-0" />
          {project.github_repo}
        </span>
      )}
      {hasDateRange && (
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3 shrink-0" />
          {project.start_date && formatDate(project.start_date)}
          {project.start_date && project.end_date && ' – '}
          {project.end_date && formatDate(project.end_date)}
        </span>
      )}
    </div>
  );
}

function ProjectActions({
  project,
  isAdmin,
}: {
  project: Project;
  isAdmin: boolean;
}): JSX.Element {
  const linkClass =
    'flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md transition-colors hover:bg-muted';

  return (
    <div className="flex items-center gap-1">
      {project.has_scorecard && (
        <Link
          to={`/scorecard/${project.id}`}
          className={cn(linkClass, 'text-primary')}
        >
          <TrendingUp className="w-3 h-3" />
          Scorecard
        </Link>
      )}
      <Link
        to={`/tracker/projects/${project.id}`}
        className={cn(linkClass, 'text-primary')}
      >
        <Wallet className="w-3 h-3" />
        Tracker
      </Link>
      {isAdmin && (
        <Link
          to={`/projects/${project.id}/edit`}
          className={cn(linkClass, 'text-muted-foreground')}
        >
          <Pencil className="w-3 h-3" />
          Edit
        </Link>
      )}
    </div>
  );
}

export default function ProjectCard({
  project,
  viewMode = 'list',
  isAdmin = false,
  score,
  costs,
}: ProjectCardProps): JSX.Element {
  if (viewMode === 'grid') {
    return (
      <Card className="hover:shadow-lg transition-shadow h-full flex flex-col">
        <div className="p-4 flex flex-col gap-2.5 flex-1">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-sm font-semibold line-clamp-2 leading-snug">
              {project.name}
            </CardTitle>
            <StatusBadge status={project.status} />
          </div>

          <ProjectMeta project={project} />

          <div className="flex-1" />

          <ProjectMetrics score={score} costs={costs} />

          <div className="pt-1.5 border-t">
            <ProjectActions project={project} isAdmin={isAdmin} />
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-sm font-semibold truncate">
                {project.name}
              </CardTitle>
              <StatusBadge status={project.status} />
            </div>
            <ProjectMeta project={project} />
          </div>

          <ProjectActions project={project} isAdmin={isAdmin} />
        </div>

        <ProjectMetrics score={score} costs={costs} />
      </div>
    </Card>
  );
}
