import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, RefreshCw, X, Info, DollarSign } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics, useUpdateEVMData } from '../hooks/useMetrics';
import { useCollectJiraMetrics, useCollectGitHubMetrics } from '../hooks/useCollectors';
import { useConfigParameters } from '../hooks/useConfig';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import EVMForm from '../components/Forms/EVMForm';
import SubIndicatorCard from '../components/SubIndicatorCard';
import type { ProjectCreate, EVMData } from '../types';
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export default function ProjectDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [isEditingEVM, setIsEditingEVM] = useState(false);
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
  const updateEVM = useUpdateEVMData(id!, metrics ?? null);

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

  const handleUpdateEVM = async (data: EVMData): Promise<void> => {
    await updateEVM.mutateAsync(data);
    setIsEditingEVM(false);
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
          <CardContent className="flex items-center gap-4">
            <div className="flex gap-2">
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
            </div>
            {metrics && (
              <span className="text-sm text-muted-foreground">
                Last collected: {new Date(metrics.created_at).toLocaleString()}
              </span>
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

      {/* EVM Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-muted-foreground" />
              <CardTitle className="text-xl">Budget & Schedule</CardTitle>
            </div>
            {!isEditingEVM && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditingEVM(true)}
                className="border border-input"
              >
                <Pencil className="w-4 h-4 mr-2" />
                {metrics?.evm_data ? 'Edit' : 'Add EVM Data'}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isEditingEVM ? (
            <EVMForm
              initialData={metrics?.evm_data}
              onSubmit={handleUpdateEVM}
              onCancel={() => setIsEditingEVM(false)}
              isLoading={updateEVM.isPending}
            />
          ) : metrics?.evm_data ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Total Budget</p>
                <p className="text-2xl font-semibold">
                  ${metrics.evm_data.budget_total.toLocaleString()}
                </p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Actual Cost</p>
                <p className="text-2xl font-semibold">
                  ${metrics.evm_data.cost_to_date.toLocaleString()}
                </p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Work Completed</p>
                <p className="text-2xl font-semibold">
                  {(metrics.evm_data.percent_completed * 100).toFixed(0)}%
                </p>
              </div>
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground">Expected Progress</p>
                <p className="text-2xl font-semibold">
                  {(metrics.evm_data.percent_planned * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground">
              No budget data available. Click "Add EVM Data" to enter budget and schedule information.
            </p>
          )}
        </CardContent>
      </Card>

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

          {scores.scores.dora && scores.scores.dora.score !== null && (
            <>
              <Separator className="my-6" />
              <div>
                <h2 className="text-2xl font-semibold mb-4">DORA Score</h2>
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">Performance</CardTitle>
                        <p className="text-sm text-muted-foreground">DevOps Research and Assessment</p>
                      </div>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button className="text-muted-foreground hover:text-foreground transition-colors">
                              <Info className="h-4 w-4" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-sm">
                              <strong>DORA metrics</strong> measure software delivery performance.
                              They track Deployment Frequency, Lead Time, Change Failure Rate, and MTTR.
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex items-center gap-4">
                        <div className="text-5xl font-bold">{scores.scores.dora.score}</div>
                        <div>
                          <span className={cn(
                            "inline-block px-3 py-1 rounded-full text-sm font-medium",
                            scores.scores.dora.classification === "Elite" && "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
                            scores.scores.dora.classification === "High" && "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
                            scores.scores.dora.classification === "Medium" && "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
                            scores.scores.dora.classification === "Low" && "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
                          )}>
                            {scores.scores.dora.classification}
                          </span>
                          <p className="text-sm text-muted-foreground mt-1">
                            {scores.scores.dora.available_metrics} of 4 metrics available
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="p-3 bg-muted rounded-lg">
                        <p className="text-xs text-muted-foreground mb-1">Deployment Frequency</p>
                        <p className="text-lg font-semibold">
                          {scores.indicators.deployment_frequency !== null
                            ? `${scores.indicators.deployment_frequency.toFixed(2)}/day`
                            : "—"}
                        </p>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <p className="text-xs text-muted-foreground mb-1">Lead Time</p>
                        <p className="text-lg font-semibold">
                          {scores.indicators.lead_time_days !== null
                            ? `${scores.indicators.lead_time_days.toFixed(1)}d`
                            : "—"}
                        </p>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <p className="text-xs text-muted-foreground mb-1">Change Failure Rate</p>
                        <p className="text-lg font-semibold">
                          {scores.indicators.change_failure_rate !== null
                            ? `${scores.indicators.change_failure_rate.toFixed(1)}%`
                            : "—"}
                        </p>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <p className="text-xs text-muted-foreground mb-1">MTTR</p>
                        <p className="text-lg font-semibold">
                          {scores.indicators.mttr_hours !== null
                            ? `${scores.indicators.mttr_hours.toFixed(1)}h`
                            : "—"}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </>
      )}

      {scores && metrics?.jira_defects && (
        <>
          <Separator className="my-6" />
          <div>
            <h2 className="text-2xl font-semibold mb-4">Metrics</h2>
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
                  ]}
                />
              )}
              {metrics.github_metrics && metrics.github_metrics.pr_size_median !== null && metrics.github_metrics.pr_size_median !== undefined && (
                <SubIndicatorCard
                  title="PR Size"
                  indicatorValue={metrics.github_metrics.pr_size_median}
                  indicatorLabel="Median lines changed"
                  indicatorSuffix=" lines"
                  description="DORA metric: Median PR size (additions + deletions)"
                  target={getTarget('PR_size_t')}
                  lowerIsBetter={true}
                  formula="median(additions + deletions)"
                  metrics={[
                    { label: 'Total Merged PRs', value: metrics.github_metrics.total_merged_prs },
                  ]}
                />
              )}
              {metrics.github_metrics && metrics.github_metrics.review_turnaround_hours !== null && metrics.github_metrics.review_turnaround_hours !== undefined && (
                <SubIndicatorCard
                  title="Review Turnaround"
                  indicatorValue={metrics.github_metrics.review_turnaround_hours}
                  indicatorLabel="Median hours to first review"
                  indicatorSuffix="h"
                  description="DORA metric: Time from PR creation to first review"
                  target={getTarget('review_turnaround_t')}
                  lowerIsBetter={true}
                  formula="median(first_review - pr_created)"
                  metrics={[
                    { label: 'Total Merged PRs', value: metrics.github_metrics.total_merged_prs },
                  ]}
                />
              )}
              {metrics.github_metrics && metrics.github_metrics.release_count_90d !== null && metrics.github_metrics.release_count_90d !== undefined && (
                <SubIndicatorCard
                  title="Deployment Frequency"
                  indicatorValue={metrics.github_metrics.release_count_90d}
                  indicatorLabel="Releases in 90 days"
                  indicatorSuffix=" releases"
                  description="DORA metric: How often deployments occur"
                  target={90}
                  lowerIsBetter={false}
                  formula="count(releases in 90d)"
                  metrics={[
                    { label: 'Per Day', value: metrics.github_metrics.deployment_frequency != null ? parseFloat(metrics.github_metrics.deployment_frequency.toFixed(2)) : null },
                  ]}
                />
              )}
              {metrics.github_metrics && metrics.github_metrics.change_failure_rate !== null && metrics.github_metrics.change_failure_rate !== undefined && (
                <SubIndicatorCard
                  title="Change Failure Rate"
                  indicatorValue={metrics.github_metrics.change_failure_rate}
                  indicatorLabel="Failure rate"
                  indicatorSuffix="%"
                  description="DORA metric: Releases requiring hotfix"
                  target={getTarget('CFR_t')}
                  lowerIsBetter={true}
                  formula="(failed / total) × 100"
                  metrics={[
                    { label: 'Total Releases', value: metrics.github_metrics.total_releases ?? null },
                    { label: 'Failed Releases', value: metrics.github_metrics.failed_releases ?? null },
                  ]}
                />
              )}
              {metrics.github_metrics && (
                <SubIndicatorCard
                  title="Security Vulnerabilities"
                  indicatorValue={metrics.github_metrics.high_severity_vulns}
                  indicatorLabel="High/Critical open >30d"
                  indicatorSuffix=""
                  description="Dependabot alerts unaddressed for 30+ days"
                  target={getTarget('HighVuln_t')}
                  lowerIsBetter={true}
                  formula="count(high/critical vulns >30d)"
                  metrics={[
                    { label: 'Total Open', value: metrics.github_metrics.high_severity_vulns_total ?? 0 },
                    { label: 'Older than 30d', value: metrics.github_metrics.high_severity_vulns },
                  ]}
                />
              )}
              {scores.indicators.post_contract_tasks !== null && (
                <SubIndicatorCard
                  title="Post-Contract Tasks"
                  indicatorValue={scores.indicators.post_contract_tasks}
                  indicatorLabel="Tasks after closure"
                  indicatorSuffix=""
                  description="New tasks created >30 days after contract end"
                  target={getTarget('post_contract_t')}
                  lowerIsBetter={true}
                  formula="count(tasks created after end_date + 30d)"
                  metrics={[
                    { label: 'Contract End', value: project.end_date ? formatDate(project.end_date) : 'Not set' },
                  ]}
                />
              )}
            </div>
          </div>
        </>
      )}

    </div>
  );
}
