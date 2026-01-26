import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Github, BarChart3, Calendar, Pencil, Trash2, X, Info, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { useProject, useReplaceProject, useDeleteProject, useUpdateProjectStatus } from '../hooks/useProjects';
import { useProjectScores } from '../hooks/useScores';
import { useProjectMetrics, useUpdateEVMData, useUpdateMilestones, useUpdateGovernance, useUpdatePMSatisfaction, useUpdateTestMaturity, useUpdateArchitecture, useUpdateStrategicImpact, useUpdateClientSurvey } from '../hooks/useMetrics';
import { useCollectJiraMetrics, useCollectGitHubMetrics } from '../hooks/useCollectors';
import { useConfigParameters } from '../hooks/useConfig';
import ScoreCard from '../components/ScoreCard/ScoreCard';
import DimensionChart from '../components/DimensionChart/DimensionChart';
import ProjectForm from '../components/Forms/ProjectForm';
import EVMForm from '../components/Forms/EVMForm';
import MilestonesForm from '../components/Forms/MilestonesForm';
import SubIndicatorCard from '../components/SubIndicatorCard';
import {
  GovernanceCard,
  PMSatisfactionCard,
  StrategicImpactCard,
  TestMaturityCard,
  ArchitectureCard,
  ClientSurveyCard,
  CollectorButtons,
  StatusControls,
} from '../components/ProjectDetail';
import type { ProjectCreate, EVMData, Milestone } from '../types';
import { Badge } from '@/components/ui/badge';
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
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showFinishDialog, setShowFinishDialog] = useState(false);
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
  const updateArchitecture = useUpdateArchitecture(id!, metrics ?? null);
  const updateProjectStatus = useUpdateProjectStatus(id!);
  const updateStrategicImpact = useUpdateStrategicImpact(id!, metrics ?? null);
  const updateClientSurvey = useUpdateClientSurvey(id!, metrics ?? null);

  const getTarget = (name: string): number | null => {
    const targets = config?.['Targets'];
    if (!targets) return null;
    const param = targets.find((p) => p.name === name);
    return param ? parseFloat(param.value) : null;
  };

  const getConstant = (name: string): number | null => {
    const constants = config?.['Gates & Constants'];
    if (!constants) return null;
    const param = constants.find((p) => p.name === name);
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
    const graceDays = getConstant('const_grace_days') ?? 3;
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
              <div className="flex items-center gap-3">
                <CardTitle className="text-3xl font-semibold">{project.name}</CardTitle>
                <Badge variant={project.status === 'finished' ? 'default' : 'secondary'} className={project.status === 'finished' ? 'bg-score-green hover:bg-score-green/80 text-white dark:text-black' : ''}>
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
                onMarkFinished={() => setShowFinishDialog(true)}
                onReopen={() => updateProjectStatus.mutateAsync('in_progress')}
                onEdit={() => setIsEditing(true)}
                onDelete={() => setShowDeleteConfirm(true)}
                isUpdatingStatus={updateProjectStatus.isPending}
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
              onCollectJira={handleCollectJiraMetrics}
              onCollectGitHub={handleCollectGitHubMetrics}
              isCollectingJira={collectJiraMetrics.isPending}
              isCollectingGitHub={collectGitHubMetrics.isPending}
              lastCollectedAt={metrics?.created_at}
            />
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

      <AlertDialog open={showFinishDialog} onOpenChange={setShowFinishDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Mark Project as Finished?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>When you mark this project as finished:</p>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Jira and GitHub collectors will be disabled</li>
                  <li>Regular metric updates will be blocked</li>
                  <li>Client Satisfaction Survey will become editable</li>
                  <li>You can reopen the project later if needed</li>
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={async () => {
                await updateProjectStatus.mutateAsync('finished');
                setShowFinishDialog(false);
              }}
              className="bg-score-green hover:bg-score-green/80 text-white dark:text-black"
            >
              Mark as Finished
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
          <Card className="bg-score-yellow/10 border-score-yellow/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-yellow">No metrics available yet</p>
              <p className="text-sm mt-1 text-score-yellow/80">
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
          <Card className="bg-score-red/10 border-score-red/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-red">Failed to collect metrics</p>
              <p className="text-sm mt-1 text-score-red/80">
                {collectJiraMetrics.error?.message || 'An unknown error occurred'}
              </p>
              {collectJiraMetrics.error?.message?.includes('authentication') && (
                <div className="mt-3 p-3 bg-score-red/10 rounded border border-score-red/30">
                  <p className="text-sm font-medium text-score-red mb-2">
                    OAuth not configured
                  </p>
                  <p className="text-xs text-score-red/80 mb-2">
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
          <Card className="bg-score-green/10 border-score-green/30">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-score-green">
                Jira metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={() => setDismissedJiraSuccess(true)}
                className="text-score-green hover:text-score-green/70"
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
          <Card className="bg-score-red/10 border-score-red/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-red">Failed to collect GitHub metrics</p>
              <p className="text-sm mt-1 text-score-red/80">
                {collectGitHubMetrics.error?.message || 'An unknown error occurred'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {collectGitHubMetrics.isSuccess && !dismissedGitHubSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-green/10 border-score-green/30">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-score-green">
                GitHub metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={() => setDismissedGitHubSuccess(true)}
                className="text-score-green hover:text-score-green/70"
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
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
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
                          <span className="text-sm text-foreground">≥{((getTarget('target_spi') ?? 1) * 100).toFixed(0)}%</span>
                        </div>
                        {metrics.evm_data.percent_planned > 0 ? (() => {
                          const spi = metrics.evm_data.percent_completed / metrics.evm_data.percent_planned;
                          const spiTarget = getTarget('target_spi') ?? 0.8;
                          return (
                            <>
                              <p className={cn(
                                "text-xl font-semibold",
                                spi >= spiTarget ? "text-score-green" :
                                spi >= spiTarget * 0.9 ? "text-score-yellow" :
                                "text-score-red"
                              )}>
                                {(spi * 100).toFixed(0)}%
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {spi > 1 ? 'Ahead of schedule' :
                                 spi === 1 ? 'On schedule' : 'Behind schedule'}
                              </p>
                            </>
                          );
                        })() : (
                          <p className="text-xl font-semibold text-muted-foreground">—</p>
                        )}
                      </div>
                      <div className="p-4 bg-muted/50 rounded-lg border">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
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
                          <span className="text-sm text-foreground">≥{((getTarget('target_cpi') ?? 1) * 100).toFixed(0)}%</span>
                        </div>
                        {metrics.evm_data.cost_to_date > 0 ? (() => {
                          const cpi = (metrics.evm_data.budget_total * metrics.evm_data.percent_completed) / metrics.evm_data.cost_to_date;
                          const cpiTarget = getTarget('target_cpi') ?? 0.8;
                          return (
                            <>
                              <p className={cn(
                                "text-xl font-semibold",
                                cpi >= cpiTarget ? "text-score-green" :
                                cpi >= cpiTarget * 0.9 ? "text-score-yellow" :
                                "text-score-red"
                              )}>
                                {(cpi * 100).toFixed(0)}%
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {cpi > 1 ? 'Under budget' :
                                 cpi === 1 ? 'On budget' : 'Over budget'}
                              </p>
                            </>
                          );
                        })() : (
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
                        {scores.indicators.on_time_milestones !== null ? (() => {
                          const milestonesTarget = (getTarget('target_milestones_on_time') ?? 85) / 100;
                          return (
                          <>
                            <p className={cn(
                              "text-xl font-semibold",
                              scores.indicators.on_time_milestones >= milestonesTarget ? "text-score-green" :
                              scores.indicators.on_time_milestones >= milestonesTarget * 0.9 ? "text-score-yellow" :
                              "text-score-red"
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
                          );
                        })() : (
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
                                          <CheckCircle2 className="w-5 h-5 text-score-green" />
                                        )}
                                        {status === 'late' && (
                                          <AlertCircle className="w-5 h-5 text-score-red" />
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
                                            ? (status === 'on-time' ? "text-score-green" : "text-score-red")
                                            : (status === 'pending' ? "text-score-green" : "text-score-red")
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
                target={getTarget('target_defect_density')}
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
                target={getTarget('target_escaped_rate')}
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
                target={getTarget('target_mttr_hours')}
                lowerIsBetter={true}
                formula="avg(resolved - created)"
                metrics={[
                  { label: 'Incidents', value: metrics.jira_defects.incidents_count },
                ]}
              />
              {metrics.flow_metrics && (
                <SubIndicatorCard
                  title="Story Review Ratio"
                  indicatorValue={scores.indicators.story_review_ratio !== null ? scores.indicators.story_review_ratio * 100 : null}
                  indicatorLabel="Stories with reviewer"
                  indicatorSuffix="%"
                  description="User stories with assigned reviewer"
                  target={100}
                  lowerIsBetter={false}
                  formula="(with_reviewer / total) × 100"
                  metrics={[
                    { label: 'With Reviewer', value: metrics.flow_metrics.stories_with_reviewer },
                    { label: 'Total Stories', value: metrics.flow_metrics.total_stories },
                  ]}
                />
              )}
              <GovernanceCard
                value={metrics?.governance_exceptions}
                target={getTarget('target_gov_exceptions') ?? 2}
                onSave={(value) => updateGovernance.mutateAsync(value)}
                isPending={updateGovernance.isPending}
              />
              <PMSatisfactionCard
                data={metrics?.pm_satisfaction}
                indicatorValue={scores.indicators.pm_satisfaction}
                target={getTarget('target_pm_satisfaction') ?? 90}
                onSave={(data) => updatePMSatisfaction.mutateAsync(data)}
                isPending={updatePMSatisfaction.isPending}
              />
              <StrategicImpactCard
                value={metrics?.strategic_impact}
                onSave={(value) => updateStrategicImpact.mutateAsync(value)}
                isPending={updateStrategicImpact.isPending}
              />
              <TestMaturityCard
                data={metrics?.test_maturity}
                indicatorValue={scores.indicators.test_maturity}
                target={getTarget('target_test_maturity') ?? 60}
                onSave={(data) => updateTestMaturity.mutateAsync(data)}
                isPending={updateTestMaturity.isPending}
              />
              <ArchitectureCard
                data={metrics?.architecture}
                indicatorValue={scores.indicators.arch_checklist}
                target={getTarget('target_architecture') ?? 100}
                onSave={(data) => updateArchitecture.mutateAsync(data)}
                isPending={updateArchitecture.isPending}
              />
              <SubIndicatorCard
                title="Lead Time"
                indicatorValue={scores.indicators.lead_time_days}
                indicatorLabel="Business days"
                indicatorSuffix="d"
                description="In Progress → Done"
                target={getTarget('target_lead_time_days')}
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
                  target={100 - (getTarget('target_pr_no_review_ratio') ?? 0)}
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
                  description="Median PR size (additions + deletions)"
                  target={getTarget('target_pr_size_lines')}
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
                  target={getTarget('target_high_vuln_count')}
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
                  target={getTarget('target_post_contract_tasks')}
                  lowerIsBetter={true}
                  formula="count(tasks created after end_date + 30d)"
                  metrics={[
                    { label: 'Contract End', value: project.end_date ? formatDate(project.end_date) : 'Not set' },
                  ]}
                />
              )}
              <ClientSurveyCard
                data={metrics?.client_survey}
                indicatorValue={scores.indicators.client_satisfaction}
                target={getTarget('target_client_satisfaction') ?? 80}
                projectStatus={project.status}
                onSave={(data) => updateClientSurvey.mutateAsync(data)}
                isPending={updateClientSurvey.isPending}
              />
            </div>
          </div>
        </>
      )}

      {scores && scores.scores.dora && scores.scores.dora.score !== null && (
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
                        scores.scores.dora.classification === "Elite" && "bg-score-green/20 text-score-green",
                        scores.scores.dora.classification === "High" && "bg-accent/20 text-accent",
                        scores.scores.dora.classification === "Medium" && "bg-score-yellow/20 text-score-yellow",
                        scores.scores.dora.classification === "Low" && "bg-score-red/20 text-score-red",
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
                    target={(getTarget('target_deployment_frequency') ?? 1) * 90}
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
                    target={getTarget('target_review_turnaround_hours')}
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
                    target={getTarget('target_change_failure_rate')}
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
                    target={getTarget('target_mttr_hours')}
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

    </div>
  );
}
