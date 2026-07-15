import { Link } from 'react-router-dom';
import { BarChart3, Github, Calendar, AlertTriangle } from 'lucide-react';
import type { Project } from '@/core/types/project';
import { formatDate } from '@/utils/formatters';
import { getStatusLabel } from '@/utils/projectStatus';
import { getScoreDotClass } from '@/utils/scoreColors';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useScoreThresholds } from '@/modules/scorecard/hooks/useConfig';

interface ProjectCardProps {
  project: Project;
  viewMode?: 'list' | 'grid';
  score?: number | null;
  latestPeriod?: string | null;
}

// Audit #17: a LIVE project whose last metrics capture is older than this
// threshold gets a warning icon — it's invisible in the global aggregate.
const STALE_METRICS_DAYS = 35;

function isMetricsStale(
  status: Project['status'],
  latestPeriod: string | null | undefined,
): boolean {
  if (status !== 'live') return false;
  if (!latestPeriod) return true;
  const match = /^(\d{4})-(\d{2})$/.exec(latestPeriod);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const captureEnd = new Date(Date.UTC(year, month, 0));
  const ageMs = Date.now() - captureEnd.getTime();
  return ageMs > STALE_METRICS_DAYS * 24 * 60 * 60 * 1000;
}

function StaleMetricsIcon({ latestPeriod }: Readonly<{ latestPeriod: string | null | undefined }>): JSX.Element {
  const label = latestPeriod
    ? `No fresh metrics since ${latestPeriod}. Re-capture from the project page.`
    : 'No metrics captured yet. Re-capture from the project page.';
  // Decorative icon: the parent Link owns navigation/keyboard interaction.
  // We render the tooltip on hover/focus of the icon via Radix' built-in
  // handlers — no extra click handler needed (avoids a11y warnings).
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="shrink-0 text-aux-yellow"
            role="img"
            aria-label={label}
          >
            <AlertTriangle className="w-4 h-4" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top">{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function ScoreBadge({ score, thresholds }: Readonly<{ score: number | null | undefined; thresholds: { green: number; yellow: number } }>): JSX.Element | null {
  if (score === null || score === undefined) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="text-sm">Score:</span>
        <span className="text-xl font-medium">—</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">Score:</span>
      <span className={cn("text-2xl font-bold font-mono tabular-nums text-foreground flex items-center gap-1.5")}>
        <span className={cn('inline-block w-2.5 h-2.5 rounded-full shrink-0', getScoreDotClass(score, thresholds))} />
        {Math.round(score)}
      </span>
    </div>
  );
}

export default function ProjectCard({ project, viewMode = 'list', score, latestPeriod }: Readonly<ProjectCardProps>): JSX.Element {
  const thresholds = useScoreThresholds();
  const hasDateRange = project.start_date || project.end_date;
  const isStale = isMetricsStale(project.status, latestPeriod);

  if (viewMode === 'grid') {
    return (
      <Link to={`/projects/${project.id}/scorecard`} className="block">
        <Card className="hover:shadow-lg transition-shadow h-full">
          <div className="p-5 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2 min-w-0 flex-1">
                <CardTitle className="text-lg font-semibold line-clamp-2">{project.name}</CardTitle>
                {isStale && <StaleMetricsIcon latestPeriod={latestPeriod} />}
              </div>
              <Badge
                variant={project.status === 'finished' ? 'default' : 'secondary'}
                className={project.status === 'finished' ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black shrink-0' : 'shrink-0'}
              >
                {getStatusLabel(project.status)}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <ScoreBadge score={score} thresholds={thresholds} />
            </div>
            <div className="space-y-1.5 text-sm text-muted-foreground">
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
          </div>
        </Card>
      </Link>
    );
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <CardTitle className="text-xl font-semibold">{project.name}</CardTitle>
            {isStale && <StaleMetricsIcon latestPeriod={latestPeriod} />}
            <Badge
              variant={project.status === 'finished' ? 'default' : 'secondary'}
              className={project.status === 'finished' ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black' : ''}
            >
              {getStatusLabel(project.status)}
            </Badge>
          </div>
          <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 text-base text-muted-foreground">
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

        <div className="flex items-center gap-6 md:flex-shrink-0">
          <ScoreBadge score={score} thresholds={thresholds} />
          <Link
            to={`/projects/${project.id}/scorecard`}
            className="text-base font-medium text-primary hover:underline"
          >
            View Details →
          </Link>
        </div>
      </div>
    </Card>
  );
}
