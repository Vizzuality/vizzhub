import { Link } from 'react-router-dom';
import {
  Calendar,
  Folder,
  Pencil,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import type { Project } from '@/core/types/project';
import type { ProjectCostSummaryLite, ProgressSummary } from '@/modules/tracker/public';
import { formatDate } from '@/utils/formatters';
import { formatCurrency } from '@/modules/tracker/public';
import { getScoreDotClass } from '@/utils/scoreColors';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { cn } from '@/lib/utils';


interface ProjectCardProps {
  readonly project: Project;
  readonly viewMode?: 'list' | 'grid';
  readonly isAdmin?: boolean;
  readonly score?: number | null;
  readonly costs?: ProjectCostSummaryLite | null;
  readonly progress?: ProgressSummary | null;
}

const SCORE_THRESHOLDS = { green: 70, yellow: 40 };

function getBurnDotClass(pct: number | null): string {
  if (pct == null) return 'bg-aux-dust-grey';
  if (pct > 100) return 'bg-aux-red';
  if (pct >= 80) return 'bg-aux-yellow';
  return 'bg-aux-neon-grass';
}

function Metric({
  label,
  value,
  muted = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly muted?: boolean;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground leading-none mb-1">
        {label}
      </div>
      <div
        className={cn(
          'text-sm font-medium leading-tight truncate',
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
  progress,
}: {
  readonly score?: number | null;
  readonly costs?: ProjectCostSummaryLite | null;
  readonly progress?: ProgressSummary | null;
}): JSX.Element | null {
  if (score == null && !costs) return null;

  return (
    <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
      {score != null && (
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground leading-none mb-1">
            Score
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className={cn('inline-block w-2 h-2 rounded-full shrink-0', getScoreDotClass(score, SCORE_THRESHOLDS))}
            />
            <span className="text-sm font-medium leading-tight">
              {Math.round(score)}
            </span>
          </div>
        </div>
      )}
      {costs && (
        <>
          <Metric
            label="Budget"
            value={costs.budget == null ? '—' : formatCurrency(costs.budget)}
            muted={costs.budget == null}
          />
          <Metric
            label="Costs"
            value={formatCurrency(costs.total_cost)}
          />
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground leading-none mb-1">
              Burn
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className={cn('inline-block w-2 h-2 rounded-full shrink-0', getBurnDotClass(costs.burn_percentage))}
              />
              <span className="text-sm font-medium leading-tight">
                {costs.burn_percentage == null
                  ? '—'
                  : `${costs.burn_percentage.toFixed(1)}%`}
              </span>
            </div>
          </div>
          <Metric
            label="Progress"
            value={progress ? `${progress.percentage.toFixed(0)}%` : '—'}
            muted={!progress}
          />
          <Metric
            label="Income"
            value={costs.income > 0 ? formatCurrency(costs.income) : '—'}
            muted={costs.income === 0}
          />
        </>
      )}
    </div>
  );
}

function ProjectMeta({ project }: { readonly project: Project }): JSX.Element | null {
  const hasDateRange = project.start_date || project.end_date;
  if (!project.program_name && !hasDateRange) return null;

  return (
    <div className="flex items-center gap-4 flex-wrap text-sm text-muted-foreground">
      {project.program_name && (
        <span className="flex items-center gap-1.5">
          <Folder className="w-4 h-4 shrink-0" />
          {project.program_name}
        </span>
      )}
      {hasDateRange && (
        <span className="flex items-center gap-1.5">
          <Calendar className="w-4 h-4 shrink-0" />
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
  readonly project: Project;
  readonly isAdmin: boolean;
}): JSX.Element {
  const linkClass =
    'flex items-center gap-1.5 text-sm font-medium px-2.5 py-1.5 rounded-md transition-colors';

  return (
    <div className="flex items-center gap-1">
      {project.has_scorecard && (
        <Link
          to={`/projects/${project.id}/scorecard`}
          className={cn(linkClass, 'text-primary hover:bg-primary/10')}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          Scorecard
        </Link>
      )}
      <Link
        to={`/projects/${project.id}/tracker`}
        className={cn(linkClass, 'text-primary hover:bg-primary/10')}
      >
        <Wallet className="w-3.5 h-3.5" />
        Tracker
      </Link>
      {isAdmin && (
        <Link
          to={`/projects/${project.id}/edit`}
          className={cn(linkClass, 'text-foreground/70 hover:bg-muted')}
        >
          <Pencil className="w-3.5 h-3.5" />
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
  progress,
}: ProjectCardProps): JSX.Element {
  if (viewMode === 'grid') {
    return (
      <Card className="hover:shadow-lg transition-shadow h-full flex flex-col">
        <div className="p-5 flex flex-col gap-3 flex-1">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg font-semibold line-clamp-2 leading-snug">
              {project.name}
            </CardTitle>
            <StatusBadge status={project.status} />
          </div>

          <ProjectMeta project={project} />

          <div className="flex-1" />

          <ProjectMetrics score={score} costs={costs} progress={progress} />

          <div className="flex items-center justify-end pt-2.5 border-t border-border/50">
            <ProjectActions project={project} isAdmin={isAdmin} />
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <CardTitle className="text-lg font-semibold truncate">
                {project.name}
              </CardTitle>
              <StatusBadge status={project.status} />
            </div>
            <ProjectMeta project={project} />
          </div>

          <div className="shrink-0">
            <ProjectActions project={project} isAdmin={isAdmin} />
          </div>
        </div>

        <ProjectMetrics score={score} costs={costs} progress={progress} />
      </div>
    </Card>
  );
}
