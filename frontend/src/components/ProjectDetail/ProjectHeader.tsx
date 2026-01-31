import { Link } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { formatDate } from '../../utils/formatters';
import StatusControls from './StatusControls';
import CollectorButtons from './CollectorButtons';
import ProjectForm from '../Forms/ProjectForm';
import type { Project, ProjectCreate } from '../../types';

interface ProjectHeaderProps {
  project: Project;
  isEditing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSubmitEdit: (data: ProjectCreate) => Promise<void>;
  isSubmitting: boolean;
  onMarkFinished: () => void;
  onReopen: () => Promise<unknown>;
  onDelete: () => void;
  isUpdatingStatus: boolean;
  onCollectMetrics: () => void;
  isCollecting: boolean;
  lastCollectedAt: string | null | undefined;
}

export default function ProjectHeader({
  project,
  isEditing,
  onEdit,
  onCancelEdit,
  onSubmitEdit,
  isSubmitting,
  onMarkFinished,
  onReopen,
  onDelete,
  isUpdatingStatus,
  onCollectMetrics,
  isCollecting,
  lastCollectedAt,
}: ProjectHeaderProps): JSX.Element {
  const hasDateRange = project.start_date || project.end_date;

  return (
    <>
      <Link
        to="/projects"
        className="inline-flex items-center gap-2 text-base text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Projects
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

            {!isEditing && (
              <StatusControls
                status={project.status}
                onMarkFinished={onMarkFinished}
                onReopen={onReopen}
                onEdit={onEdit}
                onDelete={onDelete}
                isUpdatingStatus={isUpdatingStatus}
              />
            )}
          </div>
        </CardHeader>

        {(project.jira_project_key || project.github_repo) && !isEditing && (
          <CardContent>
            <CollectorButtons
              jiraProjectKey={project.jira_project_key}
              githubRepo={project.github_repo}
              projectStatus={project.status}
              onCollectMetrics={onCollectMetrics}
              isCollecting={isCollecting}
              lastCollectedAt={lastCollectedAt}
            />
          </CardContent>
        )}

        {isEditing && (
          <CardContent>
            <ProjectForm
              project={project}
              onSubmit={onSubmitEdit}
              onCancel={onCancelEdit}
              isLoading={isSubmitting}
            />
          </CardContent>
        )}
      </Card>
    </>
  );
}
