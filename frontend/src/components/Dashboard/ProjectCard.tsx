import { Link } from 'react-router-dom';
import { BarChart3, Github, Calendar } from 'lucide-react';
import type { Project } from '../../types';
import { formatDate } from '../../utils/formatters';
import { getScoreColor } from '../../utils/scoreColors';
import { Card, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/lib/utils';
import { useScoreThresholds } from '@/hooks/useConfig';

interface ProjectCardProps {
  project: Project;
  viewMode?: 'list' | 'grid';
  score?: number | null;
}

function ScoreBadge({ score, thresholds }: { score: number | null | undefined; thresholds: { green: number; yellow: number } }): JSX.Element | null {
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
      <span className={cn("text-2xl font-bold", getScoreColor(score, thresholds))}>{Math.round(score)}</span>
    </div>
  );
}

export default function ProjectCard({ project, viewMode = 'list', score }: ProjectCardProps): JSX.Element {
  const thresholds = useScoreThresholds();
  const hasDateRange = project.start_date || project.end_date;

  if (viewMode === 'grid') {
    return (
      <Link to={`/scorecard/${project.id}`} className="block">
        <Card className="hover:shadow-lg transition-shadow h-full">
          <div className="p-5 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <CardTitle className="text-lg font-semibold line-clamp-2">{project.name}</CardTitle>
              <Badge
                variant={project.status === 'finished' ? 'default' : 'secondary'}
                className={project.status === 'finished' ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black shrink-0' : 'shrink-0'}
              >
                {project.status === 'finished' ? 'Finished' : 'In Progress'}
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
            <Badge
              variant={project.status === 'finished' ? 'default' : 'secondary'}
              className={project.status === 'finished' ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black' : ''}
            >
              {project.status === 'finished' ? 'Finished' : 'In Progress'}
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
            to={`/scorecard/${project.id}`}
            className="text-base font-medium text-primary hover:underline"
          >
            View Details →
          </Link>
        </div>
      </div>
    </Card>
  );
}
