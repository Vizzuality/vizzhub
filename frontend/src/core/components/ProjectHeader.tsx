import { Link } from 'react-router-dom';
import { Building2, Calendar, Github, BarChart3, Layers, Pencil, UserRound } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/lib/utils';
import { formatDate } from '@/utils/formatters';
import { getStatusLabel } from '@/utils/projectStatus';
import { usePermission, Action } from '@/core/permissions';
import { useProjectContext } from '@/core/contexts/ProjectContext';
import { ProjectHeaderKpis } from '@/core/components/ProjectHeaderKpis';

const STATUS_DOT: Record<string, string> = {
  proposal: 'bg-muted-foreground',
  live: 'bg-score-green',
  finished: 'bg-primary',
};

export function ProjectHeader(): JSX.Element {
  const { project } = useProjectContext();
  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canManage = usePermission(Action.PROJECTS_MANAGE);
  const canPortfolio = usePermission(Action.PORTFOLIO_VIEW) || bypassAuth;
  const hasDateRange = project.start_date || project.end_date;
  const clientName = project.client_name;

  return (
    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
      <div className="space-y-2 flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-semibold leading-tight">
            {project.name}
            {project.code && (
              <span className="block text-sm font-normal text-muted-foreground">{project.code}</span>
            )}
          </h1>
          <span className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                'inline-block w-2 h-2 rounded-full shrink-0',
                STATUS_DOT[project.status] ?? 'bg-muted-foreground',
              )}
            />
            <span className="text-sm text-foreground">{getStatusLabel(project.status)}</span>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {clientName && (
            <span className="flex items-center gap-1.5 min-w-0">
              <Building2 className="w-4 h-4 shrink-0" />
              <span className="truncate">{clientName}</span>
            </span>
          )}
          {project.program_name && (
            canPortfolio && project.program_id ? (
              <Link
                to={`/admin/portfolio/programs/${project.program_id}`}
                className="flex items-center gap-1.5 min-w-0 underline decoration-muted-foreground/40 underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground"
              >
                <Layers className="w-4 h-4 shrink-0" />
                <span className="truncate">{project.program_name}</span>
              </Link>
            ) : (
              <span className="flex items-center gap-1.5 min-w-0">
                <Layers className="w-4 h-4 shrink-0" />
                <span className="truncate">{project.program_name}</span>
              </span>
            )
          )}
          {hasDateRange && (
            <span className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4 shrink-0" />
              {project.start_date && formatDate(project.start_date)}
              {project.start_date && project.end_date && ' – '}
              {project.end_date && formatDate(project.end_date)}
            </span>
          )}
          {project.project_manager_name && (
            <span className="flex items-center gap-1.5 min-w-0">
              <UserRound className="w-4 h-4 shrink-0" />
              <span className="truncate">{project.project_manager_name}</span>
            </span>
          )}
          {project.jira_project_key && (
            <span className="flex items-center gap-1.5 min-w-0">
              <BarChart3 className="w-4 h-4 shrink-0" />
              <span className="truncate">Jira: {project.jira_project_key}</span>
            </span>
          )}
          {project.github_repo && (
            <span className="flex items-center gap-1.5 min-w-0">
              <Github className="w-4 h-4 shrink-0" />
              <span className="truncate">{project.github_repo}</span>
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6 shrink-0">
        <ProjectHeaderKpis />
        {canManage && (
          <Link to={`/projects/${project.id}/edit`}>
            <Button type="button" variant="ghost" size="sm" className="border border-input">
              <Pencil className="w-4 h-4 mr-2" /> Edit
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}
