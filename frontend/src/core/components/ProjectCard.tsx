import { Link } from 'react-router-dom';
import {
  Calendar,
  Folder,
  Pencil,
} from 'lucide-react';
import type { Project } from '@/core/types/project';
import type { ProjectCostSummaryLite, ProgressSummary } from '@/modules/tracker/public';
import { formatDate } from '@/utils/formatters';
import { formatCurrency } from '@/modules/tracker/public';
import { getBurnDotClass, getScoreDotClass } from '@/utils/scoreColors';
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

function EditLink({ project }: { readonly project: Project }): JSX.Element {
  return (
    <Link
      to={`/projects/${project.id}/edit`}
      aria-label={`Edit ${project.name}`}
      className="relative z-10 shrink-0 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
    >
      <Pencil className="w-4 h-4" />
    </Link>
  );
}

function CardLinkOverlay({ project }: { readonly project: Project }): JSX.Element {
  return (
    <Link
      to={`/projects/${project.id}`}
      aria-label={project.name}
      className="absolute inset-0 rounded-xl"
    />
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
      <Card className="relative hover:shadow-lg transition-shadow h-full flex flex-col">
        <CardLinkOverlay project={project} />
        <div className="p-5 flex flex-col gap-3 flex-1">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg font-semibold line-clamp-2 leading-snug">
              {project.name}
            </CardTitle>
            <div className="flex items-center gap-1 shrink-0">
              <StatusBadge status={project.status} />
              {isAdmin && <EditLink project={project} />}
            </div>
          </div>

          <ProjectMeta project={project} />

          <div className="flex-1" />

          <ProjectMetrics score={score} costs={costs} progress={progress} />
        </div>
      </Card>
    );
  }

  return (
    <Card className="relative hover:shadow-lg transition-shadow">
      <CardLinkOverlay project={project} />
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

          {isAdmin && (
            <div className="shrink-0">
              <EditLink project={project} />
            </div>
          )}
        </div>

        <ProjectMetrics score={score} costs={costs} progress={progress} />
      </div>
    </Card>
  );
}
