import { Link } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { formatDate } from '@/utils/formatters';
import { getStatusLabel } from '@/utils/projectStatus';
import type { Project } from '@/core/types/project';

interface ProjectHeaderProps {
  project: Project;
}

export default function ProjectHeader({
  project,
}: ProjectHeaderProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  return (
    <>
      <Link
        to="/scorecard"
        className="inline-flex items-center gap-2 text-base text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Scorecard
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3">
                <CardTitle className="text-3xl font-semibold">{project.name}</CardTitle>
                <Badge
                  variant={project.status === 'finished' ? 'default' : 'secondary'}
                  className={
                    project.status === 'finished'
                      ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black'
                      : ''
                  }
                >
                  {getStatusLabel(project.status)}
                </Badge>
              </div>
              {hasDateRange && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="w-4 h-4 shrink-0" />
                  {project.start_date && formatDate(project.start_date)}
                  {project.start_date && project.end_date && ' - '}
                  {project.end_date && formatDate(project.end_date)}
                </div>
              )}
              <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 text-base text-muted-foreground">
                {project.jira_project_key && (
                  <span className="flex items-center gap-2 min-w-0">
                    <BarChart3 className="w-5 h-5 shrink-0" />
                    <span className="truncate">Jira: {project.jira_project_key}</span>
                  </span>
                )}
                {project.github_repo && (
                  <span className="flex items-center gap-2 min-w-0">
                    <Github className="w-5 h-5 shrink-0" />
                    <span className="truncate">GitHub: {project.github_repo}</span>
                  </span>
                )}
              </div>
            </div>

            <Link to={`/projects/${project.id}/edit`}>
              <Button type="button" variant="ghost" size="sm" className="border border-input">
                <Pencil className="w-4 h-4 mr-2" />
                Edit
              </Button>
            </Link>
          </div>
        </CardHeader>
      </Card>
    </>
  );
}
