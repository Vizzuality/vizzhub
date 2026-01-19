import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, RefreshCw } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics } from '../hooks/useMetrics';
import { useCollectJiraMetrics } from '../hooks/useCollectors';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import type { ProjectCreate } from '../types';
import { formatDate } from '../utils/formatters';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: project, isLoading: projectLoading, error: projectError } = useProject(id!);
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(id!);
  const { data: metrics } = useProjectMetrics(id!);
  const replaceProject = useReplaceProject(id!);
  const deleteProject = useDeleteProject();
  const collectJiraMetrics = useCollectJiraMetrics(id!);

  const handleEdit = async (data: ProjectCreate): Promise<void> => {
    await replaceProject.mutateAsync(data);
    setIsEditing(false);
  };

  const handleDelete = async (): Promise<void> => {
    await deleteProject.mutateAsync(id!);
    navigate('/projects');
  };

  const handleCollectMetrics = async (): Promise<void> => {
    await collectJiraMetrics.mutateAsync();
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading project: {projectError?.message || 'Project not found'}
          </p>
        </CardContent>
      </Card>
    );
  }

  const hasDateRange = project.start_date || project.end_date;

  return (
    <div className="space-y-6">
      <Link
        to="/projects"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Projects
      </Link>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-1 flex-1">
              <CardTitle className="text-3xl">{project.name}</CardTitle>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                {project.jira_project_key && (
                  <span className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" />
                    Jira: {project.jira_project_key}
                  </span>
                )}
                {project.github_repo && (
                  <span className="flex items-center gap-2">
                    <Github className="w-4 h-4" />
                    GitHub: {project.github_repo}
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

            {!isEditing && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(true)}
                >
                  <Pencil className="w-4 h-4 mr-2" />
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="border-primary text-primary hover:bg-primary hover:text-primary-foreground"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </Button>
              </div>
            )}
          </div>
        </CardHeader>

        {project.jira_project_key && !isEditing && (
          <CardContent>
            <Button
              onClick={handleCollectMetrics}
              disabled={collectJiraMetrics.isPending}
            >
              <RefreshCw
                className={cn(
                  'w-4 h-4 mr-2',
                  collectJiraMetrics.isPending && 'animate-spin'
                )}
              />
              {collectJiraMetrics.isPending ? 'Collecting...' : 'Collect Metrics'}
            </Button>
          </CardContent>
        )}

        {isEditing && (
          <CardContent>
            <ProjectForm
              project={project}
              onSubmit={handleEdit}
              onCancel={() => setIsEditing(false)}
              isLoading={replaceProject.isPending}
            />
          </CardContent>
        )}
      </Card>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the project
              "{project.name}" and all associated metrics.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {scoresLoading && (
        <>
          <Separator className="my-6" />
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        </>
      )}

      {scoresError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-yellow-50 border-yellow-200">
            <CardContent className="pt-6">
              <p className="font-medium text-yellow-800">No metrics available yet</p>
              <p className="text-sm mt-1 text-yellow-700">
                {project.jira_project_key
                  ? 'Click "Collect Metrics" to fetch data from Jira.'
                  : 'Configure a Jira project key to collect metrics.'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {collectJiraMetrics.isError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-red-50 border-red-200">
            <CardContent className="pt-6">
              <p className="font-medium text-red-800">Failed to collect metrics</p>
              <p className="text-sm mt-1 text-red-700">
                {collectJiraMetrics.error?.message || 'An unknown error occurred'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {collectJiraMetrics.isSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-green-50 border-green-200">
            <CardContent className="pt-6 text-green-800">
              Metrics collected successfully! Scores are being calculated...
            </CardContent>
          </Card>
        </>
      )}

      {scores && (
        <>
          <Separator className="my-6" />
          <div>
            <h2 className="text-2xl font-bold mb-4">Scores</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ScoreCard score={scores.scores} />
              <DimensionChart scores={scores.scores.dimensions} />
            </div>
          </div>
        </>
      )}

      {metrics && (
        <>
          <Separator className="my-6" />
          <Card>
            <CardHeader>
              <CardTitle>Collected Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
            {metrics.jira_defects && (
              <div>
                <h3 className="text-sm font-medium mb-2">Jira Defects</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Bugs Closed:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.bugs_closed}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Tasks Completed:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.tasks_completed}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Escaped Defects:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.escaped_defects}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Incidents:</span>
                    <span className="ml-2 font-medium">{metrics.jira_defects.incidents_count}</span>
                  </div>
                  {metrics.jira_defects.mttr_hours !== null && (
                    <div>
                      <span className="text-muted-foreground">MTTR (hours):</span>
                      <span className="ml-2 font-medium">{metrics.jira_defects.mttr_hours}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {metrics.flow_metrics && (
              <div>
                <h3 className="text-sm font-medium mb-2">Flow Metrics</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Total Stories:</span>
                    <span className="ml-2 font-medium">{metrics.flow_metrics.total_stories}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Stories with Reviewer:</span>
                    <span className="ml-2 font-medium">{metrics.flow_metrics.stories_with_reviewer}</span>
                  </div>
                  {metrics.flow_metrics.lead_time_days !== null && (
                    <div>
                      <span className="text-muted-foreground">Lead Time (days):</span>
                      <span className="ml-2 font-medium">{metrics.flow_metrics.lead_time_days}</span>
                    </div>
                  )}
                  {metrics.flow_metrics.flow_efficiency !== null && metrics.flow_metrics.flow_efficiency !== undefined && (
                    <div>
                      <span className="text-muted-foreground">Flow Efficiency:</span>
                      <span className="ml-2 font-medium">{(metrics.flow_metrics.flow_efficiency * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {metrics.flow_metrics.commitment_reliability !== null && metrics.flow_metrics.commitment_reliability !== undefined && (
                    <div>
                      <span className="text-muted-foreground">Commitment Reliability:</span>
                      <span className="ml-2 font-medium">{(metrics.flow_metrics.commitment_reliability * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="text-xs text-muted-foreground pt-2 border-t">
              <p>Period: {formatDate(metrics.period_start)} - {formatDate(metrics.period_end)}</p>
              <p>Last updated: {new Date(metrics.created_at).toLocaleString()}</p>
            </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
