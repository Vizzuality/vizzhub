import { useState, useMemo, useEffect } from 'react';
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
import { usePrograms, useCreateProgram } from '@/core/hooks/usePrograms';
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
  links: { title: string; url: string; link_type: string }[];
}

const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: 'proposal', label: 'Proposal' },
  { value: 'live', label: 'Live' },
  { value: 'finished', label: 'Finished' },
];

const CURRENCY_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'EUR', label: 'Euro (EUR)' },
  { value: 'USD', label: 'US Dollar (USD)' },
  { value: 'GBP', label: 'British Pound (GBP)' },
  { value: 'JPY', label: 'Japanese Yen (JPY)' },
  { value: 'CHF', label: 'Swiss Franc (CHF)' },
  { value: 'CAD', label: 'Canadian Dollar (CAD)' },
  { value: 'AUD', label: 'Australian Dollar (AUD)' },
  { value: 'CNY', label: 'Chinese Yuan (CNY)' },
  { value: 'SEK', label: 'Swedish Krona (SEK)' },
  { value: 'NOK', label: 'Norwegian Krone (NOK)' },
];

const LINK_TYPE_OPTIONS = [
  { value: 'code', label: 'Code' },
  { value: 'project-management', label: 'Project Management' },
  { value: 'app-environments', label: 'App Environments' },
  { value: 'design', label: 'Design' },
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
  const createProgramMutation = useCreateProgram();
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
  const [showNewProgram, setShowNewProgram] = useState(false);
  const [newProgramName, setNewProgramName] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [proposalDialogOpen, setProposalDialogOpen] = useState(false);
  const [pendingSubmitData, setPendingSubmitData] = useState<ProjectFormData | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [formInitialized, setFormInitialized] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    control,
    setValue,
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
      links: [{ title: '', url: '', link_type: '' }],
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

  const {
    fields: linkFields,
    append: appendLink,
    remove: removeLink,
  } = useFieldArray({
    control,
    name: 'links',
  });

  const [initialLinks, setInitialLinks] = useState<{ title: string; url: string; link_type: string }[] | null>(null);
  const [linksRequested, setLinksRequested] = useState(false);

  useEffect(() => {
    if (!isEditMode || !id || linksRequested) return;
    setLinksRequested(true);
    projectsApi.getLinks(id).then((links) => {
      setInitialLinks(
        links.length > 0
          ? links.map((l) => ({ title: l.title ?? '', url: l.url ?? '', link_type: l.link_type ?? '' }))
          : [{ title: '', url: '', link_type: '' }],
      );
    }).catch(() => {
      setInitialLinks([{ title: '', url: '', link_type: '' }]);
    });
  }, [isEditMode, id, linksRequested]);

  const linksReady = !isEditMode || initialLinks !== null;

  if (isEditMode && project && !formInitialized && currentMetrics !== undefined && linksReady) {
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
      links: initialLinks ?? [{ title: '', url: '', link_type: '' }],
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

  const handleFormSubmit = (data: ProjectFormData): void => {
    setApiError(null);

    if (hasDependabotAlerts && !slackChannelId) {
      setApiError('A Slack channel is required when Dependabot Alerts are enabled.');
      return;
    }

    if (data.status === 'proposal') {
      setPendingSubmitData(data);
      setProposalDialogOpen(true);
      return;
    }

    submitForm(data);
  };

  const submitForm = async (data: ProjectFormData): Promise<void> => {
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

    const validLinks = data.links.filter((l) => l.title || l.url);

    try {
      if (isEditMode) {
        const promises: Promise<unknown>[] = [replaceMutation.mutateAsync(projectPayload)];
        if (budgetPayload) {
          promises.push(budgetMutation.mutateAsync(budgetPayload));
        }
        promises.push(projectsApi.replaceLinks(id!, validLinks));
        await Promise.all(promises);
      } else {
        const newProject = await createMutation.mutateAsync(projectPayload);
        if (newProject?.id) {
          const extraPromises: Promise<unknown>[] = [];
          if (budgetPayload) {
            extraPromises.push(projectsApi.updateBudget(newProject.id, budgetPayload));
          }
          if (validLinks.length > 0) {
            extraPromises.push(projectsApi.replaceLinks(newProject.id, validLinks));
          }
          if (extraPromises.length > 0) {
            await Promise.all(extraPromises);
          }
        }
      }
      navigateToProjects();
    } catch (error) {
      setApiError(getApiErrorMessage(error));
    }
  };

  const handleConfirmProposal = (): void => {
    setProposalDialogOpen(false);
    if (pendingSubmitData) {
      submitForm(pendingSubmitData);
      setPendingSubmitData(null);
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
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-10">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {isEditMode ? 'Edit Project' : 'New Project'}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isEditMode ? 'Update project details and budget information' : 'Set up a new project with all its details'}
          </p>
        </div>
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

      {apiError && (
        <div className="mb-6">
          <ErrorBanner message={apiError} />
        </div>
      )}

      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left column — main fields */}
          <div className="lg:col-span-2 space-y-10">

            {/* General */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">General</h2>
              <Card>
                <CardContent className="pt-6 space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="name" className="h-5 flex items-center">Name *</Label>
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
                      <Label htmlFor="code" className="h-5 flex items-center">Code *</Label>
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

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="status" className="h-5 flex items-center">Status</Label>
                      <NativeSelect id="status" className="w-full" {...register('status')}>
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </NativeSelect>
                    </div>
                    <div className="space-y-2">
                      <TooltipProvider>
                        <div className="h-5 flex items-center gap-2">
                          <Label htmlFor="currency">Currency for Invoices</Label>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button type="button" className="text-muted-foreground hover:text-foreground transition-colors">
                                <Info className="h-3.5 w-3.5" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs">
                              <p className="text-sm">Used only for invoicing. The tracker operates in EUR by default.</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </TooltipProvider>
                      <NativeSelect id="currency" className="w-full" {...register('currency')}>
                        {CURRENCY_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </NativeSelect>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <TooltipProvider>
                      <div className="h-5 flex items-center gap-2">
                        <Label htmlFor="program_id">Program</Label>
                        <span className="text-xs text-muted-foreground">(optional)</span>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button type="button" className="text-muted-foreground hover:text-foreground transition-colors">
                              <Info className="h-3.5 w-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p className="text-sm">Select if this project belongs to a program that includes several phases or contracts.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                    </TooltipProvider>
                    <div className="flex gap-3 items-start">
                      <NativeSelect id="program_id" className="flex-1" {...register('program_id')}>
                        <option value="">None</option>
                        {programs.map((program) => (
                          <option key={program.id} value={program.id}>{program.name}</option>
                        ))}
                      </NativeSelect>
                      {!showNewProgram && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowNewProgram(true)}
                          className="shrink-0 text-muted-foreground hover:text-foreground"
                        >
                          <Plus className="w-4 h-4 mr-1" />
                          New
                        </Button>
                      )}
                    </div>
                    {showNewProgram && (
                      <div className="flex gap-2 items-center">
                        <Input
                          value={newProgramName}
                          onChange={(e) => setNewProgramName(e.target.value)}
                          placeholder="Program name"
                          className="flex-1"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Escape') {
                              setShowNewProgram(false);
                              setNewProgramName('');
                            }
                          }}
                        />
                        <Button
                          type="button"
                          size="sm"
                          disabled={!newProgramName.trim() || createProgramMutation.isPending}
                          onClick={async () => {
                            const created = await createProgramMutation.mutateAsync(newProgramName.trim());
                            setValue('program_id', created.id);
                            setNewProgramName('');
                            setShowNewProgram(false);
                          }}
                        >
                          {createProgramMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            'Create'
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => { setShowNewProgram(false); setNewProgramName(''); }}
                        >
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="start_date" className="h-5 flex items-center">Start Date</Label>
                      <Input
                        id="start_date"
                        type="date"
                        min="2020-01-01"
                        max="2099-12-31"
                        {...register('start_date', {
                          pattern: { value: /^\d{4}-\d{2}-\d{2}$/, message: 'Invalid date format' },
                        })}
                      />
                      {errors.start_date && (
                        <p className="text-sm text-destructive">{errors.start_date.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="end_date" className="h-5 flex items-center">End Date</Label>
                      <Input
                        id="end_date"
                        type="date"
                        min="2020-01-01"
                        max="2099-12-31"
                        {...register('end_date', {
                          pattern: { value: /^\d{4}-\d{2}-\d{2}$/, message: 'Invalid date format' },
                          validate: (value) => {
                            if (!value || !startDate) return true;
                            return new Date(value) >= new Date(startDate) || 'End date must be on or after start date';
                          },
                        })}
                      />
                      {errors.end_date && (
                        <p className="text-sm text-destructive">{errors.end_date.message}</p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Integrations */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Integrations</h2>
              <Card>
                <CardContent className="pt-6 space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="jira_project_key" className="h-5 flex items-center">Jira Project Key</Label>
                      <Input
                        id="jira_project_key"
                        type="text"
                        placeholder="e.g., PROJ"
                        {...register('jira_project_key')}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="github_repo" className="h-5 flex items-center">GitHub Repository</Label>
                      <Input
                        id="github_repo"
                        type="text"
                        placeholder="e.g., owner/repo"
                        {...register('github_repo', {
                          pattern: { value: /^$|^[^/]+\/[^/]+$/, message: 'Format: owner/repo' },
                        })}
                      />
                      {errors.github_repo && (
                        <p className="text-sm text-destructive">{errors.github_repo.message}</p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="slack_channel" className="h-5 flex items-center">Slack Channel</Label>
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
                </CardContent>
              </Card>
            </section>

            {/* Budget & Schedule */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Budget & Schedule</h2>
              <Card>
                <CardContent className="pt-6 space-y-6">
                  <TooltipProvider>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                      {BUDGET_FIELDS.map((field) => {
                        const Icon = field.icon;
                        return (
                          <div key={field.name} className="space-y-2">
                            <div className="h-5 flex items-center gap-2">
                              <Icon className="w-4 h-4 text-muted-foreground" />
                              <Label htmlFor={field.name}>{field.label}</Label>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button type="button" className="text-muted-foreground hover:text-foreground transition-colors">
                                    <Info className="h-3.5 w-3.5" />
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
                                  max: field.max ? { value: field.max, message: `Max ${field.max}%` } : undefined,
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
                      <div className="grid grid-cols-3 gap-4 p-4 rounded-lg bg-muted/40">
                        <div>
                          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">Earned Value</p>
                          <p className="text-lg font-semibold tabular-nums">{formatCurrency(evmPreview.ev)}</p>
                        </div>
                        <div>
                          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">SPI</p>
                          {evmPreview.spi !== null ? (
                            <>
                              <p className={`text-lg font-semibold tabular-nums ${getPerformanceColor(evmPreview.spi)}`}>
                                {evmPreview.spi.toFixed(2)}
                              </p>
                              <p className="text-[11px] text-muted-foreground">{getPerformanceLabel(evmPreview.spi, 'spi')}</p>
                            </>
                          ) : (
                            <p className="text-lg font-semibold text-muted-foreground">&mdash;</p>
                          )}
                        </div>
                        <div>
                          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">CPI</p>
                          {evmPreview.cpi !== null ? (
                            <>
                              <p className={`text-lg font-semibold tabular-nums ${getPerformanceColor(evmPreview.cpi)}`}>
                                {evmPreview.cpi.toFixed(2)}
                              </p>
                              <p className="text-[11px] text-muted-foreground">{getPerformanceLabel(evmPreview.cpi, 'cpi')}</p>
                            </>
                          ) : (
                            <p className="text-lg font-semibold text-muted-foreground">&mdash;</p>
                          )}
                        </div>
                      </div>
                    )}
                  </TooltipProvider>
                </CardContent>
              </Card>
            </section>

            {/* Milestones */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Milestones</h2>
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="space-y-3">
                    {milestoneFields.map((field, index) => (
                      <div
                        key={field.id}
                        className="grid grid-cols-[1fr_150px_150px_36px] gap-3 items-end"
                      >
                        <div className="space-y-1">
                          {index === 0 && (
                            <Label className="text-xs text-muted-foreground">Name</Label>
                          )}
                          <Input
                            {...register(`milestones.${index}.name`)}
                            placeholder="e.g., MVP Release"
                          />
                        </div>
                        <div className="space-y-1">
                          {index === 0 && (
                            <Label className="text-xs text-muted-foreground">Planned</Label>
                          )}
                          <Input type="date" {...register(`milestones.${index}.planned_date`)} />
                        </div>
                        <div className="space-y-1">
                          {index === 0 && (
                            <Label className="text-xs text-muted-foreground">Actual</Label>
                          )}
                          <Input type="date" {...register(`milestones.${index}.actual_date`)} />
                        </div>
                        <div className={index === 0 ? 'pt-5' : ''}>
                          {milestoneFields.length > 1 && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => removeMilestone(index)}
                              className="h-9 w-9 text-muted-foreground hover:text-destructive"
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
                    variant="ghost"
                    size="sm"
                    onClick={() => appendMilestone({ name: '', planned_date: '', actual_date: '' })}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Milestone
                  </Button>
                </CardContent>
              </Card>
            </section>

            {/* Links */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Links</h2>
              <Card>
                <CardContent className="pt-6 space-y-3">
                  {linkFields.map((field, index) => (
                    <div
                      key={field.id}
                      className="grid grid-cols-[1fr_1fr_160px_36px] gap-3 items-end"
                    >
                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs text-muted-foreground">Title</Label>
                        )}
                        <Input
                          {...register(`links.${index}.title`)}
                          placeholder="e.g., GitHub Repo"
                        />
                      </div>
                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs text-muted-foreground">URL</Label>
                        )}
                        <Input
                          {...register(`links.${index}.url`)}
                          placeholder="https://..."
                        />
                      </div>
                      <div className="space-y-1">
                        {index === 0 && (
                          <Label className="text-xs text-muted-foreground">Type</Label>
                        )}
                        <NativeSelect
                          {...register(`links.${index}.link_type`)}
                          defaultValue={field.link_type}
                        >
                          <option value="">--</option>
                          {LINK_TYPE_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </NativeSelect>
                      </div>
                      <div className={index === 0 ? 'pt-5' : ''}>
                        {linkFields.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeLink(index)}
                            className="h-9 w-9 text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => appendLink({ title: '', url: '', link_type: '' })}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Link
                  </Button>
                </CardContent>
              </Card>
            </section>
          </div>

          {/* Right column — sidebar */}
          <div className="space-y-8">
            {/* Feature Flags */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Features</h2>
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="is_billable" className="cursor-pointer text-sm">Billable</Label>
                    <Switch id="is_billable" checked={isBillable} onCheckedChange={setIsBillable} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_scorecard" className="cursor-pointer text-sm">Scorecard</Label>
                    <Switch id="has_scorecard" checked={hasScorecard} onCheckedChange={setHasScorecard} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_dependabot_alerts" className="cursor-pointer text-sm">Dependabot Alerts</Label>
                    <Switch id="has_dependabot_alerts" checked={hasDependabotAlerts} onCheckedChange={setHasDependabotAlerts} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_budget_alerts" className="cursor-pointer text-sm">Budget Alerts</Label>
                    <Switch id="has_budget_alerts" checked={hasBudgetAlerts} onCheckedChange={setHasBudgetAlerts} />
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Notes */}
            <section>
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Notes</h2>
              <Card>
                <CardContent className="pt-6 space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="notes" className="h-5 flex items-center">Internal Notes</Label>
                    <Textarea
                      id="notes"
                      rows={3}
                      placeholder="Internal notes about this project..."
                      {...register('notes')}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="summary" className="h-5 flex items-center">Summary</Label>
                    <Textarea
                      id="summary"
                      rows={3}
                      placeholder="Brief project summary..."
                      {...register('summary')}
                    />
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* Actions — sticky on desktop */}
            <section className="lg:sticky lg:top-6">
              <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Actions</h2>
              <Card>
                <CardContent className="pt-6 space-y-3">
                  <Button
                    type="submit"
                    disabled={isMutating}
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {isMutating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                    {getSubmitButtonText(isMutating, isEditMode)}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={navigateToProjects}
                    disabled={isMutating}
                    className="w-full border border-input"
                  >
                    Cancel
                  </Button>

                  {isEditMode && (
                    <>
                      <div className="border-t border-dashed my-2" />
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setDeleteDialogOpen(true)}
                        disabled={deleteMutation.isPending}
                        className="w-full text-destructive hover:bg-destructive hover:border-destructive hover:text-white border border-input"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        {deleteMutation.isPending ? 'Deleting...' : 'Delete Project'}
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            </section>
          </div>
        </div>
      </form>

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

      <AlertDialog open={proposalDialogOpen} onOpenChange={(open) => {
        setProposalDialogOpen(open);
        if (!open) setPendingSubmitData(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Save as Proposal?</AlertDialogTitle>
            <AlertDialogDescription>
              This project will be saved with <strong>Proposal</strong> status.
              It won&apos;t appear in active project lists until its status is changed to Live.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Back to Edit</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmProposal}>
              Save as Proposal
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
