import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, RefreshCw, X } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics } from '../hooks/useMetrics';
import { useCollectJiraMetrics, useCollectGitHubMetrics } from '../hooks/useCollectors';
import { useConfigParameters } from '../hooks/useConfig';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import SubIndicatorCard from '../components/SubIndicatorCard';
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
  const [dismissedJiraSuccess, setDismissedJiraSuccess] = useState(false);
  const [dismissedGitHubSuccess, setDismissedGitHubSuccess] = useState(false);

  const { data: project, isLoading: projectLoading, error: projectError } = useProject(id!);
  const { data: scores, isLoading: scoresLoading, error: scoresError } = useProjectScores(id!);
  const { data: metrics } = useProjectMetrics(id!);
  const { data: config } = useConfigParameters();
  const replaceProject = useReplaceProject(id!);
  const deleteProject = useDeleteProject();
  const collectJiraMetrics = useCollectJiraMetrics(id!);
  const collectGitHubMetrics = useCollectGitHubMetrics(id!);

  const getTarget = (name: string): number | null => {
    const targets = config?.['Targets'];
    if (!targets) return null;
    const param = targets.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  const handleEdit = async (data: ProjectCreate): Promise<void> => {
    await replaceProject.mutateAsync(data);
    setIsEditing(false);
  };

  const handleDelete = async (): Promise<void> => {
    await deleteProject.mutateAsync(id!);
    navigate('/projects');
  };

  const handleCollectJiraMetrics = async (): Promise<void> => {
    setDismissedJiraSuccess(false);
    await collectJiraMetrics.mutateAsync();
  };

  const handleCollectGitHubMetrics = async (): Promise<void> => {
    setDismissedGitHubSuccess(false);
    await collectGitHubMetrics.mutateAsync();
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

        {(project.jira_project_key || project.github_repo) && !isEditing && (
          <CardContent className="flex gap-2">
            {project.jira_project_key && (
              <Button
                onClick={handleCollectJiraMetrics}
                disabled={collectJiraMetrics.isPending}
                variant="outline"
              >
                <RefreshCw
                  className={cn(
                    'w-4 h-4 mr-2',
                    collectJiraMetrics.isPending && 'animate-spin'
                  )}
                />
                {collectJiraMetrics.isPending ? 'Collecting Jira...' : 'Collect Jira'}
              </Button>
            )}
            {project.github_repo && (
              <Button
                onClick={handleCollectGitHubMetrics}
                disabled={collectGitHubMetrics.isPending}
                variant="outline"
              >
                <Github
                  className={cn(
                    'w-4 h-4 mr-2',
                    collectGitHubMetrics.isPending && 'animate-spin'
                  )}
                />
                {collectGitHubMetrics.isPending ? 'Collecting GitHub...' : 'Collect GitHub'}
              </Button>
            )}
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

      {collectJiraMetrics.isSuccess && !dismissedJiraSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-green-800 dark:text-green-200">
                Jira metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={() => setDismissedJiraSuccess(true)}
                className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-200"
              >
                <X className="w-5 h-5" />
              </button>
            </CardContent>
          </Card>
        </>
      )}

      {collectGitHubMetrics.isError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800">
            <CardContent className="pt-6">
              <p className="font-medium text-red-800 dark:text-red-200">Failed to collect GitHub metrics</p>
              <p className="text-sm mt-1 text-red-700 dark:text-red-300">
                {collectGitHubMetrics.error?.message || 'An unknown error occurred'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {collectGitHubMetrics.isSuccess && !dismissedGitHubSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-green-800 dark:text-green-200">
                GitHub metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={() => setDismissedGitHubSuccess(true)}
                className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-200"
              >
                <X className="w-5 h-5" />
              </button>
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

      {scores && metrics?.jira_defects && (
        <>
          <Separator className="my-6" />
          <div>
            <h2 className="text-2xl font-semibold mb-4">Sub-indicators</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <SubIndicatorCard
                title="Defect Density"
                indicatorValue={scores.indicators.defect_density}
                indicatorLabel="Bugs per 100 tasks"
                indicatorSuffix="%"
                description="Ratio of bugs to completed tasks"
                target={getTarget('DefDensity_t')}
                lowerIsBetter={true}
                formula="(Bugs / Tasks) × 100"
                metrics={[
                  { label: 'Bugs', value: metrics.jira_defects.bugs_total },
                  { label: 'Tasks Completed', value: metrics.jira_defects.tasks_completed },
                ]}
              />
              <SubIndicatorCard
                title="Escaped Rate"
                indicatorValue={scores.indicators.escaped_rate}
                indicatorLabel="Escaped per 100 tasks"
                indicatorSuffix="%"
                description="Bugs found in Staging/Production"
                target={getTarget('Escaped_t')}
                lowerIsBetter={true}
                formula="(Escaped / Tasks) × 100"
                metrics={[
                  { label: 'Escaped Defects', value: metrics.jira_defects.escaped_defects },
                  { label: 'Tasks Completed', value: metrics.jira_defects.tasks_completed },
                ]}
              />
              <SubIndicatorCard
                title="MTTR"
                indicatorValue={scores.indicators.mttr_hours}
                indicatorLabel="Business hours"
                indicatorSuffix="h"
                description="Mean Time To Repair"
                target={getTarget('MTTR_t')}
                lowerIsBetter={true}
                formula="avg(resolved - created)"
                metrics={[
                  { label: 'Incidents', value: metrics.jira_defects.incidents_count },
                ]}
              />
              <SubIndicatorCard
                title="Lead Time"
                indicatorValue={scores.indicators.lead_time_days}
                indicatorLabel="Business days"
                indicatorSuffix="d"
                description="In Progress → Done"
                target={getTarget('LT_t')}
                lowerIsBetter={true}
                formula="avg(done - in_progress)"
                metrics={[
                  { label: 'Issues', value: metrics.flow_metrics?.lead_time_sample_size ?? null },
                ]}
              />
              <SubIndicatorCard
                title="Commitment Reliability"
                indicatorValue={scores.indicators.commitment_reliability !== null ? scores.indicators.commitment_reliability * 100 : null}
                indicatorLabel="Single-sprint ratio"
                indicatorSuffix="%"
                description="Issues completed in original sprint"
                target={100}
                lowerIsBetter={false}
                formula="single_sprint / committed"
                metrics={[
                  { label: 'Committed', value: metrics.flow_metrics?.committed_issues ?? null },
                  { label: 'Single Sprint', value: metrics.flow_metrics?.single_sprint_issues ?? null },
                  { label: 'Multi Sprint', value: metrics.flow_metrics?.multi_sprint_issues ?? null },
                ]}
              />
              {metrics.github_metrics && (
                <SubIndicatorCard
                  title="PR Review Coverage"
                  indicatorValue={
                    metrics.github_metrics.pr_review_ratio !== null && metrics.github_metrics.pr_review_ratio !== undefined
                      ? metrics.github_metrics.pr_review_ratio * 100
                      : null
                  }
                  indicatorLabel="Review coverage"
                  indicatorSuffix="%"
                  description="PRs reviewed before merge"
                  target={100 - (getTarget('PR_noReview_t') ?? 0)}
                  lowerIsBetter={false}
                  formula="(reviewed / total) × 100"
                  metrics={[
                    { label: 'Reviewed', value: metrics.github_metrics.total_merged_prs - metrics.github_metrics.prs_without_review },
                    { label: 'Total Merged', value: metrics.github_metrics.total_merged_prs },
                    { label: 'Without Review', value: metrics.github_metrics.prs_without_review },
                  ]}
                />
              )}
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
                    <span className="text-sm text-muted-foreground">Bugs</span>
                    <span className="text-base font-medium">{metrics.jira_defects.bugs_total}</span>
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
                  {metrics.flow_metrics.commitment_reliability !== null && metrics.flow_metrics.commitment_reliability !== undefined && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">Commitment Reliability</span>
                      <span className="text-base font-medium">{(metrics.flow_metrics.commitment_reliability * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {metrics.github_metrics && (
              <div>
                <h3 className="text-base font-medium mb-3">GitHub Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">PRs Without Review</span>
                    <span className="text-base font-medium">{metrics.github_metrics.prs_without_review}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">Total Merged PRs</span>
                    <span className="text-base font-medium">{metrics.github_metrics.total_merged_prs}</span>
                  </div>
                  {metrics.github_metrics.pr_review_ratio !== null && metrics.github_metrics.pr_review_ratio !== undefined && (
                    <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                      <span className="text-sm text-muted-foreground">PR Review Ratio</span>
                      <span className="text-base font-medium">{(metrics.github_metrics.pr_review_ratio * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  <div className="flex justify-between items-center p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">High Severity Vulns</span>
                    <span className="text-base font-medium">{metrics.github_metrics.high_severity_vulns}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="text-xs text-muted-foreground pt-2 border-t">
              <p>Data as of: {new Date(metrics.created_at).toLocaleString()}</p>
            </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
