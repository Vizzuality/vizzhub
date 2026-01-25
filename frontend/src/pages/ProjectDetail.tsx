import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, RefreshCw, X, Info, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics, useUpdateEVMData, useUpdateMilestones, useUpdateGovernance, useUpdatePMSatisfaction, useUpdateTestMaturity } from '../hooks/useMetrics';
import { useCollectJiraMetrics, useCollectGitHubMetrics } from '../hooks/useCollectors';
import { useConfigParameters } from '../hooks/useConfig';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import EVMForm from '../components/Forms/EVMForm';
import MilestonesForm from '../components/Forms/MilestonesForm';
import SubIndicatorCard from '../components/SubIndicatorCard';
import type { ProjectCreate, EVMData, Milestone } from '../types';
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
  const [isEditingMilestones, setIsEditingMilestones] = useState(false);
  const [showMilestones, setShowMilestones] = useState(false);
  const [isEditingGovernance, setIsEditingGovernance] = useState(false);
  const [governanceValue, setGovernanceValue] = useState<string>('');
  const [isEditingPMSatisfaction, setIsEditingPMSatisfaction] = useState(false);
  const [pmSatisfactionForm, setPMSatisfactionForm] = useState<{
    delivery_complaints: 'yes' | 'no' | '-';
    design_complaints: 'yes' | 'no' | '-';
    overall_estimation: string;
  }>({ delivery_complaints: '-', design_complaints: '-', overall_estimation: '' });
  const [isEditingTestMaturity, setIsEditingTestMaturity] = useState(false);
  const [testMaturityForm, setTestMaturityForm] = useState<{
    e2e?: number;
    unit?: number;
    accessibility?: number;
    security?: number;
    frontend?: number;
  }>({});
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
  const updateMilestones = useUpdateMilestones(id!, metrics ?? null);
  const updateGovernance = useUpdateGovernance(id!, metrics ?? null);
  const updatePMSatisfaction = useUpdatePMSatisfaction(id!, metrics ?? null);
  const updateTestMaturity = useUpdateTestMaturity(id!, metrics ?? null);

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

  const handleUpdateMilestones = async (data: Milestone[]): Promise<void> => {
    await updateMilestones.mutateAsync(data);
    setIsEditingMilestones(false);
  };

  const handleDeleteMilestone = async (index: number): Promise<void> => {
    if (!metrics?.milestones) return;
    const updated = metrics.milestones.filter((_, i) => i !== index);
    await updateMilestones.mutateAsync(updated);
  };

  const getMilestoneStatus = (milestone: Milestone): 'on-time' | 'late' | 'pending' => {
    const today = new Date();
    const planned = new Date(milestone.planned_date);
    const graceDays = 3;
    const graceDate = new Date(planned);
    graceDate.setDate(graceDate.getDate() + graceDays);

    if (milestone.actual_date) {
      const actual = new Date(milestone.actual_date);
      return actual <= graceDate ? 'on-time' : 'late';
    }
    return today > graceDate ? 'late' : 'pending';
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

          {/* EVM Section - Budget & Schedule */}
          <Separator className="my-6" />
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-semibold">Budget & Schedule</h2>
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
            <Card>
              <CardContent className="pt-6">
                {isEditingEVM ? (
                  <EVMForm
                    initialData={metrics?.evm_data}
                    onSubmit={handleUpdateEVM}
                    onCancel={() => setIsEditingEVM(false)}
                    isLoading={updateEVM.isPending}
                  />
                ) : metrics?.evm_data ? (
                  <div className="space-y-4">
                    {/* Input Values */}
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
                    {/* Calculated Values + Milestones */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="p-4 bg-muted/50 rounded-lg border">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm text-muted-foreground">Earned Value (EV)</p>
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Budget × Work Completed</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                        <p className="text-xl font-semibold">
                          ${(metrics.evm_data.budget_total * metrics.evm_data.percent_completed).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </p>
                      </div>
                      <div className="p-4 bg-muted/50 rounded-lg border">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm text-muted-foreground">Schedule Performance (SPI)</p>
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Work Completed / Expected Progress</p>
                                <p className="text-xs text-white/70 mt-1">&gt;1 = ahead, 1 = on track, &lt;1 = behind</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                        {metrics.evm_data.percent_planned > 0 ? (
                          <>
                            <p className={cn(
                              "text-xl font-semibold",
                              metrics.evm_data.percent_completed / metrics.evm_data.percent_planned >= 1 ? "text-green-600 dark:text-green-400" :
                              metrics.evm_data.percent_completed / metrics.evm_data.percent_planned >= 0.9 ? "text-yellow-600 dark:text-yellow-400" :
                              "text-red-600 dark:text-red-400"
                            )}>
                              {(metrics.evm_data.percent_completed / metrics.evm_data.percent_planned).toFixed(2)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {metrics.evm_data.percent_completed / metrics.evm_data.percent_planned > 1 ? 'Ahead of schedule' :
                               metrics.evm_data.percent_completed / metrics.evm_data.percent_planned === 1 ? 'On schedule' : 'Behind schedule'}
                            </p>
                          </>
                        ) : (
                          <p className="text-xl font-semibold text-muted-foreground">—</p>
                        )}
                      </div>
                      <div className="p-4 bg-muted/50 rounded-lg border">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm text-muted-foreground">Cost Performance (CPI)</p>
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Earned Value / Actual Cost</p>
                                <p className="text-xs text-white/70 mt-1">&gt;1 = under budget, 1 = on budget, &lt;1 = over budget</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                        {metrics.evm_data.cost_to_date > 0 ? (
                          <>
                            <p className={cn(
                              "text-xl font-semibold",
                              (metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date >= 1 ? "text-green-600 dark:text-green-400" :
                              (metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date >= 0.9 ? "text-yellow-600 dark:text-yellow-400" :
                              "text-red-600 dark:text-red-400"
                            )}>
                              {((metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date).toFixed(2)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {(metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date > 1 ? 'Under budget' :
                               (metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date === 1 ? 'On budget' : 'Over budget'}
                            </p>
                          </>
                        ) : (
                          <p className="text-xl font-semibold text-muted-foreground">—</p>
                        )}
                      </div>
                      {/* Milestones Card */}
                      <button
                        onClick={() => setShowMilestones(!showMilestones)}
                        className="p-4 bg-muted/50 rounded-lg border text-left hover:bg-muted/70 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm text-muted-foreground">On-Time Milestones</p>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="text-muted-foreground">
                                    <Info className="h-3 w-3" />
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p className="text-sm">On-time delivery rate</p>
                                  <p className="text-xs text-white/70 mt-1">Target: 85%</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                          {showMilestones ? (
                            <ChevronUp className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                          )}
                        </div>
                        {scores.indicators.on_time_milestones !== null ? (
                          <>
                            <p className={cn(
                              "text-xl font-semibold",
                              scores.indicators.on_time_milestones >= 0.85 ? "text-green-600 dark:text-green-400" :
                              scores.indicators.on_time_milestones >= 0.7 ? "text-yellow-600 dark:text-yellow-400" :
                              "text-red-600 dark:text-red-400"
                            )}>
                              {(scores.indicators.on_time_milestones * 100).toFixed(0)}%
                            </p>
                            <div className="flex justify-between items-center">
                              <p className="text-xs text-muted-foreground">
                                {metrics?.milestones?.length || 0} milestone{(metrics?.milestones?.length || 0) !== 1 ? 's' : ''}
                              </p>
                              <p className="text-xs text-chart-3">expand to edit</p>
                            </div>
                          </>
                        ) : (
                          <>
                            <p className="text-xl font-semibold text-muted-foreground">—</p>
                            <div className="flex justify-between items-center">
                              <p className="text-xs text-muted-foreground">No milestones</p>
                              <p className="text-xs text-chart-3">expand to edit</p>
                            </div>
                          </>
                        )}
                      </button>
                    </div>

                    {/* Expanded Milestones List */}
                    {showMilestones && (
                      <div className="mt-4">
                        {isEditingMilestones ? (
                          <MilestonesForm
                            initialData={metrics?.milestones}
                            onSubmit={handleUpdateMilestones}
                            onCancel={() => setIsEditingMilestones(false)}
                            isLoading={updateMilestones.isPending}
                          />
                        ) : (
                          <>
                            {metrics?.milestones && metrics.milestones.length > 0 ? (
                              <div className="space-y-2">
                                {metrics.milestones.map((milestone, index) => {
                                  const status = getMilestoneStatus(milestone);
                                  return (
                                    <div
                                      key={index}
                                      className="flex items-center justify-between p-3 bg-muted/50 rounded-lg group"
                                    >
                                      <div className="flex items-center gap-3">
                                        {status === 'on-time' && (
                                          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                                        )}
                                        {status === 'late' && (
                                          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                                        )}
                                        {status === 'pending' && (
                                          <Clock className="w-5 h-5 text-muted-foreground" />
                                        )}
                                        <span className="font-medium">{milestone.name}</span>
                                      </div>
                                      <div className="flex items-center gap-4 text-sm">
                                        <span className="text-muted-foreground">
                                          Planned: {new Date(milestone.planned_date).toLocaleDateString()}
                                        </span>
                                        <span className={cn(
                                          milestone.actual_date
                                            ? (status === 'on-time' ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400")
                                            : (status === 'pending' ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400")
                                        )}>
                                          Actual: {milestone.actual_date
                                            ? new Date(milestone.actual_date).toLocaleDateString()
                                            : "--/--/----"}
                                        </span>
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                                          onClick={() => handleDeleteMilestone(index)}
                                          disabled={updateMilestones.isPending}
                                        >
                                          <Trash2 className="w-4 h-4" />
                                        </Button>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <p className="text-muted-foreground">
                                No milestones defined yet.
                              </p>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setIsEditingMilestones(true)}
                              className="mt-4 border border-input"
                            >
                              <Pencil className="w-4 h-4 mr-2" />
                              {metrics?.milestones?.length ? 'Edit Milestones' : 'Add Milestones'}
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No budget data available. Click "Add EVM Data" to enter budget and schedule information.
                  </p>
                )}
              </CardContent>
            </Card>
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
                  </CardContent>
                </Card>

                {/* DORA Sub-indicators */}
                {metrics?.github_metrics && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    {metrics.github_metrics.release_count_90d !== null && metrics.github_metrics.release_count_90d !== undefined && (
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
                    {metrics.github_metrics.review_turnaround_hours !== null && metrics.github_metrics.review_turnaround_hours !== undefined && (
                      <SubIndicatorCard
                        title="Lead Time (Review Turnaround)"
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
                    {metrics.github_metrics.change_failure_rate !== null && metrics.github_metrics.change_failure_rate !== undefined && (
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
                    {scores.indicators.mttr_hours !== null && (
                      <SubIndicatorCard
                        title="MTTR"
                        indicatorValue={scores.indicators.mttr_hours}
                        indicatorLabel="Mean Time to Recovery"
                        indicatorSuffix="h"
                        description="DORA metric: Time to restore service after incident"
                        target={getTarget('MTTR_t')}
                        lowerIsBetter={true}
                        formula="avg(resolved_at - created_at)"
                        metrics={[
                          { label: 'Incidents', value: metrics.jira_defects?.incidents_count ?? 0 },
                        ]}
                      />
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}

      {scores && metrics?.jira_defects && (
        <>
          <Separator className="my-6" />
          <div>
            <h2 className="text-2xl font-semibold mb-4">Quality & Security Metrics</h2>
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
              {/* Governance Compliance - Editable */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">Governance Compliance</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Exceptions from latest peer review
                      </p>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-muted-foreground hover:text-foreground transition-colors">
                            <Info className="h-4 w-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="font-mono text-xs">score = 1 - (exceptions / target)</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
                    {isEditingGovernance ? (
                      <div className="space-y-3">
                        <div>
                          <label className="text-sm font-medium text-muted-foreground">
                            Number of unjustified exceptions
                          </label>
                          <input
                            type="number"
                            min="0"
                            value={governanceValue}
                            onChange={(e) => setGovernanceValue(e.target.value)}
                            className="mt-1 w-full px-3 py-2 border rounded-md bg-background"
                            placeholder="0"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={async () => {
                              const value = parseInt(governanceValue) || 0;
                              await updateGovernance.mutateAsync(value);
                              setIsEditingGovernance(false);
                            }}
                            disabled={updateGovernance.isPending}
                          >
                            {updateGovernance.isPending ? 'Saving...' : 'Save'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setIsEditingGovernance(false);
                              setGovernanceValue(metrics?.governance_exceptions?.toString() ?? '');
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-muted-foreground">
                            Exceptions count
                          </span>
                          <span className={cn(
                            'text-3xl font-bold',
                            metrics?.governance_exceptions === undefined || metrics?.governance_exceptions === null
                              ? 'text-muted-foreground'
                              : metrics.governance_exceptions === 0
                              ? 'text-green-600 dark:text-green-400'
                              : metrics.governance_exceptions <= (getTarget('GovExc_t') ?? 2)
                              ? 'text-yellow-600 dark:text-yellow-400'
                              : 'text-red-600 dark:text-red-400'
                          )}>
                            {metrics?.governance_exceptions ?? '—'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between pt-2 border-t border-border/50">
                          <span className="text-xs text-muted-foreground">KPI</span>
                          <span className="text-sm text-foreground">
                            ≤{getTarget('GovExc_t') ?? 2} exceptions
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                  {!isEditingGovernance && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setGovernanceValue(metrics?.governance_exceptions?.toString() ?? '');
                        setIsEditingGovernance(true);
                      }}
                    >
                      <Pencil className="w-4 h-4 mr-2" />
                      {metrics?.governance_exceptions !== undefined && metrics?.governance_exceptions !== null ? 'Edit' : 'Add'} Exceptions
                    </Button>
                  )}
                </CardContent>
              </Card>
              {/* PM Satisfaction Estimation - Editable */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">Client Satisfaction (PM Est.)</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        PM estimation of client satisfaction
                      </p>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-muted-foreground hover:text-foreground transition-colors">
                            <Info className="h-4 w-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="font-mono text-xs">0.3×delivery + 0.3×design + 0.4×overall</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
                    {isEditingPMSatisfaction ? (
                      <div className="space-y-4">
                        <div>
                          <label className="text-sm font-medium text-muted-foreground">
                            Has the client complained about delays or delivery quality?
                          </label>
                          <div className="flex gap-2 mt-2">
                            {(['no', 'yes', '-'] as const).map((value) => (
                              <Button
                                key={value}
                                size="sm"
                                variant={pmSatisfactionForm.delivery_complaints === value ? 'default' : 'outline'}
                                onClick={() => setPMSatisfactionForm(prev => ({ ...prev, delivery_complaints: value }))}
                              >
                                {value === '-' ? 'N/A' : value === 'no' ? 'No' : 'Yes'}
                              </Button>
                            ))}
                          </div>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-muted-foreground">
                            Has the client expressed unresolved dissatisfaction with design/implementation?
                          </label>
                          <div className="flex gap-2 mt-2">
                            {(['no', 'yes', '-'] as const).map((value) => (
                              <Button
                                key={value}
                                size="sm"
                                variant={pmSatisfactionForm.design_complaints === value ? 'default' : 'outline'}
                                onClick={() => setPMSatisfactionForm(prev => ({ ...prev, design_complaints: value }))}
                              >
                                {value === '-' ? 'N/A' : value === 'no' ? 'No' : 'Yes'}
                              </Button>
                            ))}
                          </div>
                        </div>
                        <div>
                          <label className="text-sm font-medium text-muted-foreground">
                            Overall estimation of client satisfaction (1-5)
                          </label>
                          <div className="flex gap-2 mt-2">
                            {[1, 2, 3, 4, 5].map((value) => (
                              <Button
                                key={value}
                                size="sm"
                                variant={pmSatisfactionForm.overall_estimation === value.toString() ? 'default' : 'outline'}
                                onClick={() => setPMSatisfactionForm(prev => ({ ...prev, overall_estimation: value.toString() }))}
                              >
                                {value}
                              </Button>
                            ))}
                          </div>
                        </div>
                        <div className="flex gap-2 pt-2">
                          <Button
                            size="sm"
                            onClick={async () => {
                              await updatePMSatisfaction.mutateAsync({
                                delivery_complaints: pmSatisfactionForm.delivery_complaints,
                                design_complaints: pmSatisfactionForm.design_complaints,
                                overall_estimation: pmSatisfactionForm.overall_estimation ? parseInt(pmSatisfactionForm.overall_estimation) : undefined,
                              });
                              setIsEditingPMSatisfaction(false);
                            }}
                            disabled={updatePMSatisfaction.isPending}
                          >
                            {updatePMSatisfaction.isPending ? 'Saving...' : 'Save'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setIsEditingPMSatisfaction(false);
                              setPMSatisfactionForm({
                                delivery_complaints: metrics?.pm_satisfaction?.delivery_complaints ?? '-',
                                design_complaints: metrics?.pm_satisfaction?.design_complaints ?? '-',
                                overall_estimation: metrics?.pm_satisfaction?.overall_estimation?.toString() ?? '',
                              });
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-muted-foreground">
                            Normalized score
                          </span>
                          <span className={cn(
                            'text-3xl font-bold',
                            scores.indicators.pm_satisfaction === null
                              ? 'text-muted-foreground'
                              : scores.indicators.pm_satisfaction >= 0.8
                              ? 'text-green-600 dark:text-green-400'
                              : scores.indicators.pm_satisfaction >= 0.6
                              ? 'text-yellow-600 dark:text-yellow-400'
                              : 'text-red-600 dark:text-red-400'
                          )}>
                            {scores.indicators.pm_satisfaction !== null
                              ? (scores.indicators.pm_satisfaction * 100).toFixed(0) + '%'
                              : '—'}
                          </span>
                        </div>
                        {metrics?.pm_satisfaction && (
                          <div className="space-y-1 pt-2 border-t border-border/50">
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Delivery complaints</span>
                              <span className={cn(
                                metrics.pm_satisfaction.delivery_complaints === 'no' ? 'text-green-600' :
                                metrics.pm_satisfaction.delivery_complaints === 'yes' ? 'text-red-600' : ''
                              )}>
                                {metrics.pm_satisfaction.delivery_complaints === '-' ? 'N/A' : metrics.pm_satisfaction.delivery_complaints}
                              </span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Design complaints</span>
                              <span className={cn(
                                metrics.pm_satisfaction.design_complaints === 'no' ? 'text-green-600' :
                                metrics.pm_satisfaction.design_complaints === 'yes' ? 'text-red-600' : ''
                              )}>
                                {metrics.pm_satisfaction.design_complaints === '-' ? 'N/A' : metrics.pm_satisfaction.design_complaints}
                              </span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">Overall (1-5)</span>
                              <span>{metrics.pm_satisfaction.overall_estimation ?? '—'}</span>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  {!isEditingPMSatisfaction && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setPMSatisfactionForm({
                          delivery_complaints: metrics?.pm_satisfaction?.delivery_complaints ?? '-',
                          design_complaints: metrics?.pm_satisfaction?.design_complaints ?? '-',
                          overall_estimation: metrics?.pm_satisfaction?.overall_estimation?.toString() ?? '',
                        });
                        setIsEditingPMSatisfaction(true);
                      }}
                    >
                      <Pencil className="w-4 h-4 mr-2" />
                      {metrics?.pm_satisfaction ? 'Edit' : 'Add'} Estimation
                    </Button>
                  )}
                </CardContent>
              </Card>
              {/* Test Maturity - Editable */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">Test Maturity</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Automated testing coverage assessment
                      </p>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-muted-foreground hover:text-foreground transition-colors">
                            <Info className="h-4 w-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="font-mono text-xs">weighted avg of 5 test types</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
                    {isEditingTestMaturity ? (
                      <div className="space-y-4">
                        {([
                          { key: 'e2e', label: 'E2E Tests' },
                          { key: 'unit', label: 'Unit Tests' },
                          { key: 'accessibility', label: 'Accessibility Tests' },
                          { key: 'security', label: 'Security Tests' },
                          { key: 'frontend', label: 'Frontend Tests' },
                        ] as const).map(({ key, label }) => (
                          <div key={key}>
                            <label className="text-sm font-medium text-muted-foreground">{label}</label>
                            <div className="flex gap-2 mt-2">
                              {([
                                { value: 0, label: 'None' },
                                { value: 1, label: 'Minimal' },
                                { value: 3, label: 'Adequate' },
                                { value: 5, label: 'Comprehensive' },
                              ]).map((option) => (
                                <Button
                                  key={option.value}
                                  size="sm"
                                  variant={testMaturityForm[key] === option.value ? 'default' : 'outline'}
                                  onClick={() => setTestMaturityForm(prev => ({ ...prev, [key]: option.value }))}
                                  className="flex-1"
                                >
                                  {option.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        ))}
                        <div className="flex gap-2 pt-2">
                          <Button
                            size="sm"
                            onClick={async () => {
                              await updateTestMaturity.mutateAsync(testMaturityForm);
                              setIsEditingTestMaturity(false);
                            }}
                            disabled={updateTestMaturity.isPending}
                          >
                            {updateTestMaturity.isPending ? 'Saving...' : 'Save'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setIsEditingTestMaturity(false);
                              setTestMaturityForm(metrics?.test_maturity ?? {});
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-muted-foreground">
                            Weighted score
                          </span>
                          <span className={cn(
                            'text-3xl font-bold',
                            scores.indicators.test_maturity === null
                              ? 'text-muted-foreground'
                              : scores.indicators.test_maturity >= 0.8
                              ? 'text-green-600 dark:text-green-400'
                              : scores.indicators.test_maturity >= 0.6
                              ? 'text-yellow-600 dark:text-yellow-400'
                              : 'text-red-600 dark:text-red-400'
                          )}>
                            {scores.indicators.test_maturity !== null
                              ? (scores.indicators.test_maturity * 100).toFixed(0) + '%'
                              : '—'}
                          </span>
                        </div>
                        {metrics?.test_maturity && (
                          <div className="space-y-1 pt-2 border-t border-border/50">
                            {([
                              { key: 'e2e', label: 'E2E' },
                              { key: 'unit', label: 'Unit' },
                              { key: 'accessibility', label: 'Accessibility' },
                              { key: 'security', label: 'Security' },
                              { key: 'frontend', label: 'Frontend' },
                            ] as const).map(({ key, label }) => {
                              const value = metrics.test_maturity?.[key];
                              const levelLabel = value === 0 ? 'None' : value === 1 ? 'Minimal' : value === 3 ? 'Adequate' : value === 5 ? 'Comprehensive' : '—';
                              return (
                                <div key={key} className="flex justify-between text-xs">
                                  <span className="text-muted-foreground">{label}</span>
                                  <span className={cn(
                                    value === 5 ? 'text-green-600' :
                                    value === 3 ? 'text-yellow-600' :
                                    value === 1 ? 'text-orange-600' :
                                    value === 0 ? 'text-red-600' : ''
                                  )}>
                                    {levelLabel}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  {!isEditingTestMaturity && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setTestMaturityForm(metrics?.test_maturity ?? {});
                        setIsEditingTestMaturity(true);
                      }}
                    >
                      <Pencil className="w-4 h-4 mr-2" />
                      {metrics?.test_maturity ? 'Edit' : 'Add'} Assessment
                    </Button>
                  )}
                </CardContent>
              </Card>
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
