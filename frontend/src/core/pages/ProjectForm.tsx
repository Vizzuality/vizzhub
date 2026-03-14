import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm, useFieldArray } from 'react-hook-form';
import type { ProjectCreate, ProjectStatus, ProgramSummary } from '@/core/types/project';
import {
  useProject,
  useCreateProject,
  useReplaceProject,
  useDeleteProject,
  useUpdateProjectStatus,
} from '@/core/hooks/useProjects';
import { usePrograms } from '@/core/hooks/usePrograms';
import { useSlackChannels } from '@/core/hooks/useSlackChannels';
import {
  useCurrentPeriodMetrics,
  useUpdateProjectBudget,
  buildBudgetPayload,
} from '@/core/hooks/useProjectBudget';
import { projectsApi } from '@/core/services/projects';
import {
  calculateEVMValues,
  formatCurrency,
  getPerformanceColor,
  getPerformanceLabel,
} from '@/shared/utils/evmCalculations';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Switch } from '@/shared/components/ui/switch';
import { NativeSelect } from '@/shared/components/ui/native-select';
import { SlackChannelCombobox } from '@/shared/components/ui/SlackChannelCombobox';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { ErrorBanner } from '@/shared/components/ui/error-banner';
import {
  Trash2,
  CheckCircle,
  RotateCcw,
  Lock,
  Loader2,
  Plus,
  Info,
  Calculator,
  DollarSign,
  TrendingUp,
  Clock,
  Flag,
  Calendar,
} from 'lucide-react';

interface ProjectFormData {
  name: string;
  code: string;
  status: ProjectStatus;
  currency: string;
  program_id: string;
  jira_project_key: string;
  github_repo: string;
  start_date: string;
  end_date: string;
  notes: string;
  summary: string;
  budget_total: string;
  cost_to_date: string;
  percent_completed: string;
  percent_planned: string;
  milestones: { name: string; planned_date: string; actual_date: string }[];
}

const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: 'proposal', label: 'Proposal' },
  { value: 'live', label: 'Live' },
  { value: 'finished', label: 'Finished' },
];

const CURRENCY_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'USD', label: 'Dollar (USD)' },
  { value: 'EUR', label: 'Euro (EUR)' },
];

interface BudgetFieldConfig {
  name: 'budget_total' | 'cost_to_date' | 'percent_completed' | 'percent_planned';
  label: string;
  icon: typeof DollarSign;
  tooltip: string;
  placeholder: string;
  suffix?: string;
  max?: number;
}

const BUDGET_FIELDS: BudgetFieldConfig[] = [
  {
    name: 'budget_total',
    label: 'Total Budget',
    icon: DollarSign,
    tooltip: 'The total planned budget for the entire project (Planned Value)',
    placeholder: 'e.g., 100000',
  },
  {
    name: 'cost_to_date',
    label: 'Actual Cost',
    icon: TrendingUp,
    tooltip: 'The actual expenses incurred to date (Actual Cost)',
    placeholder: 'e.g., 45000',
  },
  {
    name: 'percent_completed',
    label: 'Work Completed',
    icon: Calculator,
    tooltip: 'Estimated percentage of the total work completed (0-100%)',
    placeholder: 'e.g., 50',
    suffix: '%',
    max: 100,
  },
  {
    name: 'percent_planned',
    label: 'Expected Progress',
    icon: Clock,
    tooltip: 'Percentage of work that should be done by now according to schedule (0-100%)',
    placeholder: 'e.g., 45',
    suffix: '%',
    max: 100,
  },
];

function getSubmitButtonText(isPending: boolean, isEditMode: boolean): string {
  if (isPending) {
    return isEditMode ? 'Saving...' : 'Creating...';
  }
  return isEditMode ? 'Save Changes' : 'Create Project';
}

function getApiErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred. Please try again.';
}

export default function ProjectForm(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditMode = !!id;

  const { data: project, isLoading: isLoadingProject, isError: isProjectError } =
    useProject(id ?? '');
  const { data: programsData } = usePrograms();
  const programs: ProgramSummary[] = programsData ?? [];
  const { data: currentMetrics } = useCurrentPeriodMetrics(id ?? '');

  const createMutation = useCreateProject();
  const replaceMutation = useReplaceProject(id ?? '');
  const deleteMutation = useDeleteProject();
  const statusMutation = useUpdateProjectStatus(id ?? '');
  const budgetMutation = useUpdateProjectBudget(id ?? '');

  const {
    channels,
    isLoading: isLoadingChannels,
    isSlackConfigured,
    isCheckingStatus,
  } = useSlackChannels();

  const [slackChannelId, setSlackChannelId] = useState<string>('');
  const [isBillable, setIsBillable] = useState<boolean>(true);
  const [hasScorecard, setHasScorecard] = useState<boolean>(true);
  const [hasDependabotAlerts, setHasDependabotAlerts] = useState<boolean>(true);
  const [hasBudgetAlerts, setHasBudgetAlerts] = useState<boolean>(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [formInitialized, setFormInitialized] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    control,
    formState: { errors },
  } = useForm<ProjectFormData>({
    defaultValues: {
      name: '',
      code: '',
      status: 'proposal',
      currency: '',
      program_id: '',
      jira_project_key: '',
      github_repo: '',
      start_date: '',
      end_date: '',
      notes: '',
      summary: '',
      budget_total: '',
      cost_to_date: '',
      percent_completed: '',
      percent_planned: '',
      milestones: [{ name: '', planned_date: '', actual_date: '' }],
    },
  });

  const {
    fields: milestoneFields,
    append: appendMilestone,
    remove: removeMilestone,
  } = useFieldArray({
    control,
    name: 'milestones',
  });

  if (isEditMode && project && !formInitialized && currentMetrics !== undefined) {
    const metricsEvm = currentMetrics?.evm_data;
    const metricsMilestones = currentMetrics?.milestones;

    reset({
      name: project.name,
      code: project.code ?? '',
      status: project.status,
      currency: project.currency ?? '',
      program_id: project.program_id ?? '',
      jira_project_key: project.jira_project_key ?? '',
      github_repo: project.github_repo ?? '',
      start_date: project.start_date ?? '',
      end_date: project.end_date ?? '',
      notes: project.notes ?? '',
      summary: project.summary ?? '',
      budget_total: metricsEvm?.budget_total?.toString() ?? '',
      cost_to_date: metricsEvm?.cost_to_date?.toString() ?? '',
      percent_completed: metricsEvm?.percent_completed
        ? (metricsEvm.percent_completed * 100).toString()
        : '',
      percent_planned: metricsEvm?.percent_planned
        ? (metricsEvm.percent_planned * 100).toString()
        : '',
      milestones: metricsMilestones?.length
        ? metricsMilestones.map((m: { name: string; planned_date: string; actual_date?: string }) => ({
            name: m.name,
            planned_date: m.planned_date,
            actual_date: m.actual_date ?? '',
          }))
        : [{ name: '', planned_date: '', actual_date: '' }],
    });
    setSlackChannelId(project.slack_channel_id ?? '');
    setIsBillable(project.is_billable);
    setHasScorecard(project.has_scorecard);
    setHasDependabotAlerts(project.has_dependabot_alerts);
    setHasBudgetAlerts(project.has_budget_alerts);
    setFormInitialized(true);
  }

  const startDate = watch('start_date');
  const currentStatus = watch('status');
  const watchedBudgetTotal = watch('budget_total');
  const watchedCostToDate = watch('cost_to_date');
  const watchedPercentCompleted = watch('percent_completed');
  const watchedPercentPlanned = watch('percent_planned');

  const evmPreview = useMemo(() => {
    const budget = Number.parseFloat(watchedBudgetTotal) || 0;
    const cost = Number.parseFloat(watchedCostToDate) || 0;
    const completed = (Number.parseFloat(watchedPercentCompleted) || 0) / 100;
    const planned = (Number.parseFloat(watchedPercentPlanned) || 0) / 100;
    return calculateEVMValues(budget, cost, completed, planned);
  }, [watchedBudgetTotal, watchedCostToDate, watchedPercentCompleted, watchedPercentPlanned]);

  const isMutating = createMutation.isPending || replaceMutation.isPending || budgetMutation.isPending;

  const navigateToProjects = (): void => {
    navigate('/projects');
  };

  const handleFormSubmit = async (data: ProjectFormData): Promise<void> => {
    setApiError(null);

    const projectPayload: ProjectCreate = {
      name: data.name,
      code: data.code,
      status: data.status,
      is_billable: isBillable,
      has_scorecard: hasScorecard,
      has_dependabot_alerts: hasDependabotAlerts,
      has_budget_alerts: hasBudgetAlerts,
      currency: data.currency || null,
      program_id: data.program_id || null,
      jira_project_key: data.jira_project_key || undefined,
      github_repo: data.github_repo || undefined,
      slack_channel_id: slackChannelId || undefined,
      start_date: data.start_date?.trim() || undefined,
      end_date: data.end_date?.trim() || undefined,
      notes: data.notes?.trim() || null,
      summary: data.summary?.trim() || null,
    };

    const budgetPayload = buildBudgetPayload(
      {
        budget_total: data.budget_total,
        cost_to_date: data.cost_to_date,
        percent_completed: data.percent_completed,
        percent_planned: data.percent_planned,
      },
      data.milestones,
    );

    try {
      if (isEditMode) {
        const promises: Promise<unknown>[] = [replaceMutation.mutateAsync(projectPayload)];
        if (budgetPayload) {
          promises.push(budgetMutation.mutateAsync(budgetPayload));
        }
        await Promise.all(promises);
      } else {
        const newProject = await createMutation.mutateAsync(projectPayload);
        if (budgetPayload && newProject?.id) {
          await projectsApi.updateBudget(newProject.id, budgetPayload);
        }
      }
      navigateToProjects();
    } catch (error) {
      setApiError(getApiErrorMessage(error));
    }
  };

  const handleDelete = (e: React.MouseEvent): void => {
    e.preventDefault();
    if (!id) return;
    setApiError(null);

    deleteMutation.mutate(id, {
      onSuccess: () => {
        setDeleteDialogOpen(false);
        navigateToProjects();
      },
      onError: (error) => {
        setDeleteDialogOpen(false);
        setApiError(getApiErrorMessage(error));
      },
    });
  };

  const handleMarkFinished = (): void => {
    if (!id) return;
    setApiError(null);

    statusMutation.mutate(
      { status: 'finished', finished_at: new Date().toISOString().split('T')[0] },
      {
        onError: (error) => setApiError(getApiErrorMessage(error)),
      },
    );
  };

  const handleReopen = (): void => {
    if (!id) return;
    setApiError(null);

    statusMutation.mutate(
      { status: 'live' },
      {
        onError: (error) => setApiError(getApiErrorMessage(error)),
      },
    );
  };

  if (isEditMode && isLoadingProject) {
    return <LoadingSpinner />;
  }

  if (isEditMode && isProjectError) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <ErrorBanner message="Failed to load project. It may not exist or you may not have access." />
        <div className="mt-4">
          <Button variant="ghost" onClick={navigateToProjects} className="border border-input">
            Back to Projects
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{isEditMode ? 'Edit Project' : 'Create Project'}</CardTitle>
            {isEditMode && (
              <div className="flex gap-2">
                {currentStatus !== 'finished' && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={handleMarkFinished}
                    disabled={statusMutation.isPending}
                    className="border border-input text-score-green hover:bg-score-green hover:border-score-green hover:text-black"
                  >
                    <CheckCircle className="w-4 h-4 mr-2" />
                    {statusMutation.isPending ? 'Updating...' : 'Mark as Finished'}
                  </Button>
                )}
                {currentStatus === 'finished' && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={handleReopen}
                    disabled={statusMutation.isPending}
                    className="border border-input text-score-green hover:bg-score-green hover:border-score-green hover:text-black"
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    {statusMutation.isPending ? 'Updating...' : 'Reopen Project'}
                  </Button>
                )}
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {apiError && (
            <div className="mb-4">
              <ErrorBanner message={apiError} />
            </div>
          )}

          <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  type="text"
                  {...register('name', { required: 'Project name is required' })}
                />
                {errors.name && (
                  <p className="text-sm text-destructive">{errors.name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  type="text"
                  placeholder="e.g., PRJ-001"
                  {...register('code', { required: 'Project code is required' })}
                />
                {errors.code && (
                  <p className="text-sm text-destructive">{errors.code.message}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="status">Status</Label>
                <NativeSelect id="status" className="w-full" {...register('status')}>
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <NativeSelect id="currency" className="w-full" {...register('currency')}>
                  {CURRENCY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="program_id">Program</Label>
                <NativeSelect id="program_id" className="w-full" {...register('program_id')}>
                  <option value="">None</option>
                  {programs.map((program) => (
                    <option key={program.id} value={program.id}>
                      {program.name}
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-3 pt-6">
                <div className="flex items-center gap-3">
                  <Switch
                    id="is_billable"
                    checked={isBillable}
                    onCheckedChange={setIsBillable}
                  />
                  <Label htmlFor="is_billable" className="cursor-pointer">
                    Billable
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id="has_scorecard"
                    checked={hasScorecard}
                    onCheckedChange={setHasScorecard}
                  />
                  <Label htmlFor="has_scorecard" className="cursor-pointer">
                    Scorecard
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id="has_dependabot_alerts"
                    checked={hasDependabotAlerts}
                    onCheckedChange={setHasDependabotAlerts}
                  />
                  <Label htmlFor="has_dependabot_alerts" className="cursor-pointer">
                    Dependabot Alerts
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id="has_budget_alerts"
                    checked={hasBudgetAlerts}
                    onCheckedChange={setHasBudgetAlerts}
                  />
                  <Label htmlFor="has_budget_alerts" className="cursor-pointer">
                    Budget Alerts
                  </Label>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="jira_project_key">Jira Project Key</Label>
                <Input
                  id="jira_project_key"
                  type="text"
                  placeholder="e.g., PROJ"
                  {...register('jira_project_key')}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="github_repo">GitHub Repository</Label>
                <Input
                  id="github_repo"
                  type="text"
                  placeholder="e.g., owner/repo"
                  {...register('github_repo', {
                    pattern: {
                      value: /^$|^[^/]+\/[^/]+$/,
                      message: 'Format: owner/repo',
                    },
                  })}
                />
                {errors.github_repo && (
                  <p className="text-sm text-destructive">{errors.github_repo.message}</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="slack_channel">Slack Channel</Label>
              {isCheckingStatus && (
                <div className="flex items-center gap-2 h-9 px-3 text-sm text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Checking Slack configuration...
                </div>
              )}
              {!isCheckingStatus && !isSlackConfigured && (
                <div className="flex items-center gap-2 h-9 px-3 text-sm text-muted-foreground border border-input rounded-md bg-muted/50">
                  <Lock className="w-4 h-4" />
                  Slack is not configured
                </div>
              )}
              {!isCheckingStatus && isSlackConfigured && (
                <SlackChannelCombobox
                  id="slack_channel"
                  value={slackChannelId}
                  onValueChange={setSlackChannelId}
                  channels={channels}
                  disabled={isLoadingChannels}
                  placeholder={isLoadingChannels ? 'Loading channels...' : 'Select a channel'}
                  includeNone
                  className="w-full"
                />
              )}
              <p className="text-xs text-muted-foreground">
                Select a channel to receive project notifications
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_date">Start Date</Label>
                <Input
                  id="start_date"
                  type="date"
                  min="2020-01-01"
                  max="2099-12-31"
                  {...register('start_date', {
                    pattern: {
                      value: /^\d{4}-\d{2}-\d{2}$/,
                      message: 'Invalid date format',
                    },
                  })}
                />
                {errors.start_date && (
                  <p className="text-sm text-destructive">{errors.start_date.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="end_date">End Date</Label>
                <Input
                  id="end_date"
                  type="date"
                  min="2020-01-01"
                  max="2099-12-31"
                  {...register('end_date', {
                    pattern: {
                      value: /^\d{4}-\d{2}-\d{2}$/,
                      message: 'Invalid date format',
                    },
                    validate: (value) => {
                      if (!value || !startDate) return true;
                      return (
                        new Date(value) >= new Date(startDate) ||
                        'End date must be on or after start date'
                      );
                    },
                  })}
                />
                {errors.end_date && (
                  <p className="text-sm text-destructive">{errors.end_date.message}</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                rows={3}
                placeholder="Internal notes about this project..."
                {...register('notes')}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="summary">Summary</Label>
              <Textarea
                id="summary"
                rows={3}
                placeholder="Brief project summary..."
                {...register('summary')}
              />
            </div>

            {/* Budget & Schedule */}
            <TooltipProvider>
              <div className="space-y-4 pt-2 border-t">
                <h3 className="text-base font-semibold">Budget & Schedule</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {BUDGET_FIELDS.map((field) => {
                    const Icon = field.icon;
                    return (
                      <div key={field.name} className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 text-muted-foreground" />
                          <Label htmlFor={field.name}>{field.label}</Label>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground transition-colors"
                              >
                                <Info className="h-4 w-4" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs">
                              <p className="text-sm">{field.tooltip}</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <div className="relative">
                          <Input
                            id={field.name}
                            type="number"
                            step="any"
                            min="0"
                            max={field.max}
                            placeholder={field.placeholder}
                            {...register(field.name, {
                              min: { value: 0, message: 'Must be positive' },
                              max: field.max
                                ? { value: field.max, message: `Max ${field.max}%` }
                                : undefined,
                            })}
                            className={field.suffix ? 'pr-8' : ''}
                          />
                          {field.suffix && (
                            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                              {field.suffix}
                            </span>
                          )}
                        </div>
                        {errors[field.name] && (
                          <p className="text-sm text-destructive">{errors[field.name]?.message}</p>
                        )}
                      </div>
                    );
                  })}
                </div>

                {evmPreview.hasData && (
                  <Card className="bg-muted/50">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Calculator className="w-4 h-4" />
                        Calculated Values
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="p-3 bg-background rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="text-xs text-muted-foreground">Earned Value (EV)</p>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button type="button" className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Budget x Work Completed</p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <p className="text-lg font-semibold">{formatCurrency(evmPreview.ev)}</p>
                        </div>

                        <div className="p-3 bg-background rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="text-xs text-muted-foreground">Schedule Performance (SPI)</p>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button type="button" className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Work Completed / Expected Progress</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                  &gt;1 = ahead, 1 = on track, &lt;1 = behind
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          {evmPreview.spi !== null ? (
                            <>
                              <p className={`text-lg font-semibold ${getPerformanceColor(evmPreview.spi)}`}>
                                {evmPreview.spi.toFixed(2)}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {getPerformanceLabel(evmPreview.spi, 'spi')}
                              </p>
                            </>
                          ) : (
                            <p className="text-lg font-semibold text-muted-foreground">—</p>
                          )}
                        </div>

                        <div className="p-3 bg-background rounded-lg">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="text-xs text-muted-foreground">Cost Performance (CPI)</p>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button type="button" className="text-muted-foreground">
                                  <Info className="h-3 w-3" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="text-sm">Earned Value / Actual Cost</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                  &gt;1 = under budget, 1 = on budget, &lt;1 = over budget
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          {evmPreview.cpi !== null ? (
                            <>
                              <p className={`text-lg font-semibold ${getPerformanceColor(evmPreview.cpi)}`}>
                                {evmPreview.cpi.toFixed(2)}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {getPerformanceLabel(evmPreview.cpi, 'cpi')}
                              </p>
                            </>
                          ) : (
                            <p className="text-lg font-semibold text-muted-foreground">—</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Milestones */}
              <div className="space-y-4 pt-2 border-t">
                <h3 className="text-base font-semibold">Milestones</h3>

                <div className="space-y-3">
                  {milestoneFields.map((field, index) => (
                    <div
                      key={field.id}
                      className="grid grid-cols-[1fr_140px_140px_40px] gap-3 items-end p-3 bg-muted/50 rounded-lg"
                    >
                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs flex items-center gap-1">
                            <Flag className="w-3 h-3" />
                            Milestone Name
                          </Label>
                        )}
                        <Input
                          {...register(`milestones.${index}.name`)}
                          placeholder="e.g., MVP Release"
                        />
                      </div>

                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            Planned
                          </Label>
                        )}
                        <Input
                          type="date"
                          {...register(`milestones.${index}.planned_date`)}
                        />
                      </div>

                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            Actual
                          </Label>
                        )}
                        <Input
                          type="date"
                          {...register(`milestones.${index}.actual_date`)}
                        />
                      </div>

                      <div className={index === 0 ? 'pt-5' : ''}>
                        {milestoneFields.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeMilestone(index)}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => appendMilestone({ name: '', planned_date: '', actual_date: '' })}
                  className="w-full"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Milestone
                </Button>
              </div>
            </TooltipProvider>

            <div className="flex flex-col gap-4 pt-4 border-t">
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={navigateToProjects}
                  disabled={isMutating}
                  className="border border-input"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isMutating}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  {isMutating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  {getSubmitButtonText(isMutating, isEditMode)}
                </Button>
              </div>

              {isEditMode && (
                <div className="flex flex-col items-center gap-3 pt-6 mt-2 border-t border-dashed">
                  <span className="text-sm text-muted-foreground">Danger Zone</span>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setDeleteDialogOpen(true)}
                    disabled={deleteMutation.isPending}
                    className="border border-input text-destructive hover:bg-destructive hover:border-destructive hover:text-white"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {deleteMutation.isPending ? 'Deleting...' : 'Delete Project'}
                  </Button>
                </div>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the project
              and all associated data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
