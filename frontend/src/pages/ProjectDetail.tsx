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
        className="inline-flex items-center gap-2 text-base text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Projects
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3 flex-1">
              <CardTitle className="text-3xl font-semibold">{project.name}</CardTitle>
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
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  onClick={() => setIsEditing(true)}
                  className="border border-input"
                >
                  <Pencil className="w-5 h-5 mr-2" />
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="border border-input text-destructive hover:bg-destructive hover:text-destructive-foreground"
                >
                  <Trash2 className="w-5 h-5 mr-2" />
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
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
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
          <Card className="bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800">
            <CardContent className="pt-6">
              <p className="font-medium text-red-800 dark:text-red-200">Failed to collect metrics</p>
              <p className="text-sm mt-1 text-red-700 dark:text-red-300">
                {collectJiraMetrics.error?.message || 'An unknown error occurred'}
              </p>
              {collectJiraMetrics.error?.message?.includes('authentication') && (
                <div className="mt-3 p-3 bg-red-100 dark:bg-red-900 rounded border border-red-300 dark:border-red-700">
                  <p className="text-sm font-medium text-red-900 dark:text-red-100 mb-2">
                    OAuth not configured
                  </p>
                  <p className="text-xs text-red-800 dark:text-red-200 mb-2">
                    You need to authorize Jira OAuth to collect metrics. This only needs to be done once.
                  </p>
                  <a
                    href="http://localhost:8000/api/oauth/jira/authorize"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block text-xs font-medium text-primary hover:underline"
                  >
                    → Authorize Jira OAuth
                  </a>
                </div>
              )}
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
            <h2 className="text-2xl font-semibold mb-4">Scores</h2>
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
                <h3 className="text-base font-medium mb-3">Jira Defects</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Bugs Closed</span>
                    <span className="text-base font-medium">{metrics.jira_defects.bugs_closed}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Tasks Completed</span>
                    <span className="text-base font-medium">{metrics.jira_defects.tasks_completed}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Escaped Defects</span>
                    <span className="text-base font-medium">{metrics.jira_defects.escaped_defects}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Incidents</span>
                    <span className="text-base font-medium">{metrics.jira_defects.incidents_count}</span>
                  </div>
                  {metrics.jira_defects.mttr_hours !== null && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">MTTR (hours)</span>
                      <span className="text-base font-medium">{metrics.jira_defects.mttr_hours}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {metrics.flow_metrics && (
              <div>
                <h3 className="text-base font-medium mb-3">Flow Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Total Stories</span>
                    <span className="text-base font-medium">{metrics.flow_metrics.total_stories}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Stories with Reviewer</span>
                    <span className="text-base font-medium">{metrics.flow_metrics.stories_with_reviewer}</span>
                  </div>
                  {metrics.flow_metrics.lead_time_days !== null && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">Lead Time (days)</span>
                      <span className="text-base font-medium">{metrics.flow_metrics.lead_time_days}</span>
                    </div>
                  )}
                  {metrics.flow_metrics.flow_efficiency !== null && metrics.flow_metrics.flow_efficiency !== undefined && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">Flow Efficiency</span>
                      <span className="text-base font-medium">{(metrics.flow_metrics.flow_efficiency * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {metrics.flow_metrics.commitment_reliability !== null && metrics.flow_metrics.commitment_reliability !== undefined && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">Commitment Reliability</span>
                      <span className="text-base font-medium">{(metrics.flow_metrics.commitment_reliability * 100).toFixed(1)}%</span>
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
