import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useNavigationGuard } from '@/core/contexts/NavigationGuardContext';
import { useForm, useFieldArray, Controller, type Control } from 'react-hook-form';
import type {
  BudgetPreviewResponse,
  ProjectCreate,
  ProjectStatus,
  ProgramSummary,
} from '@/core/types/project';
import {
  useProject,
  useCreateProject,
  useReplaceProject,
  useDeleteProject,
  useUpdateProjectStatus,
} from '@/core/hooks/useProjects';
import { usePrograms, useCreateProgram } from '@/core/hooks/usePrograms';
import { useSlackChannels } from '@/core/hooks/useSlackChannels';
import { useUserSummaries } from '@/core/hooks/useUsers';
import { getFullName } from '@/utils/formatters';
import {
  useCurrentPeriodMetrics,
  useUpdateProjectBudget,
} from '@/core/hooks/useProjectBudget';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { projectsApi } from '@/core/services/projects';
import { useBudgetLines, useReplaceBudgetLines } from '@/modules/tracker/hooks/useBudgetLines';
import { useProjectSettings, useUpdateProjectSettings } from '@/modules/tracker/hooks/useProjectCosts';
import { useClientOptions } from '@/modules/portfolio/hooks/useClientOptions';
import { useBudgetPreview } from '@/core/hooks/useBudgetPreview';
import { trackerApi } from '@/modules/tracker/services/tracker';
import BudgetLinesEditor from '@/modules/tracker/components/BudgetLinesEditor';
import type { BudgetLineCreate } from '@/modules/tracker/types/tracker';
import { DATE_INPUT_MIN, DATE_INPUT_MAX } from '@/shared/constants/dates';
import { formatCurrency, formatAmount } from '@/shared/utils/evmCalculations';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Switch } from '@/shared/components/ui/switch';
import { NativeSelect } from '@/shared/components/ui/native-select';
import { SlackChannelCombobox } from '@/shared/components/ui/SlackChannelCombobox';
import { cn } from '@/lib/utils';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
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
  Check,
  ChevronsUpDown,
} from 'lucide-react';

interface ProjectFormData {
  name: string;
  code: string;
  status: ProjectStatus;
  currency: string;
  program_id: string;
  project_manager_id: string;
  client_id: string;
  jira_project_key: string;
  github_repo: string;
  start_date: string;
  end_date: string;
  notes: string;
  summary: string;
  original_budget: string;
  contract_rate: string;
  milestones: { name: string; planned_date: string; actual_date: string }[];
  links: { title: string; url: string; link_type: string }[];
}

const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: 'proposal', label: 'Proposal' },
  { value: 'live', label: 'Live' },
  { value: 'finished', label: 'Finished' },
];

function buildCurrencyOptions(dbCodes: string[]): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = [
    { value: 'dollar', label: 'US Dollar (USD)' },
    { value: 'euro', label: 'Euro (EUR)' },
  ];
  const skip = new Set(['USD', 'EUR']);
  for (const code of dbCodes) {
    if (!skip.has(code)) {
      opts.push({ value: code, label: code });
    }
  }
  return opts;
}

const LINK_TYPE_OPTIONS = [
  { value: 'code', label: 'Code' },
  { value: 'project-management', label: 'Project Management' },
  { value: 'app-environments', label: 'App Environments' },
  { value: 'design', label: 'Design' },
];

const EMPTY_MILESTONE = { name: '', planned_date: '', actual_date: '' };
const EMPTY_LINK = { title: '', url: '', link_type: '' };

interface ProjectData {
  name: string;
  code?: string | null;
  status: ProjectStatus;
  currency: string;
  program_id?: string | null;
  project_manager_id?: string | null;
  client_id?: string | null;
  jira_project_key?: string | null;
  github_repo?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  notes?: string | null;
  summary?: string | null;
  budget?: number | null;
  original_budget?: number | null;
}

function buildFormDefaults(
  project: ProjectData,
  milestones: { name: string; planned_date: string; actual_date?: string }[] | undefined,
  links: { title: string; url: string; link_type: string }[] | null,
  contractRate?: number,
): ProjectFormData {
  return {
    name: project.name,
    code: project.code ?? '',
    status: project.status,
    currency: project.currency,
    program_id: project.program_id ?? '',
    project_manager_id: project.project_manager_id ?? '',
    client_id: project.client_id ?? '',
    jira_project_key: project.jira_project_key ?? '',
    github_repo: project.github_repo ?? '',
    start_date: project.start_date ?? '',
    end_date: project.end_date ?? '',
    notes: project.notes ?? '',
    summary: project.summary ?? '',
    // Fallback to budget (EUR) only for legacy projects predating the 2026-05-31
    // original_budget backfill; all active projects now have original_budget populated.
    original_budget: (project.original_budget ?? project.budget)?.toString() ?? '',
    contract_rate: contractRate?.toString() ?? '175',
    milestones: milestones?.length
      ? milestones.map((m) => ({
          name: m.name,
          planned_date: m.planned_date,
          actual_date: m.actual_date ?? '',
        }))
      : [{ ...EMPTY_MILESTONE }],
    links: links ?? [{ ...EMPTY_LINK }],
  };
}

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

function sanitizeAmount(input: string): string {
  let raw = input.replaceAll(/[^\d.]/g, '');
  const firstDot = raw.indexOf('.');
  if (firstDot !== -1) {
    raw = raw.slice(0, firstDot + 1) + raw.slice(firstDot + 1).replaceAll('.', '');
  }
  return raw;
}

function deriveBudgetPreviewState(
  query: UseQueryResult<BudgetPreviewResponse>,
  originalBudget: string,
  currency: string,
  startDate: string,
): { previewEur: number | null | undefined; noRate: boolean } {
  const previewEur = query.data?.budget_eur;
  const hasInputs =
    !!originalBudget && Number.parseFloat(originalBudget) > 0 && !!currency && !!startDate;
  const noRate = hasInputs && !query.isLoading && query.isFetched && previewEur == null;
  return { previewEur, noRate };
}

function formatBudgetEur(isLoading: boolean, previewEur: number | null | undefined): string {
  if (isLoading) return 'Calculating…';
  if (previewEur != null) return formatCurrency(previewEur, 'EUR');
  return '—';
}

function CurrencyAmountInput({
  id,
  value,
  onChange,
  currency,
  placeholder,
}: Readonly<{
  id: string;
  value: string;
  onChange: (value: string) => void;
  currency: string;
  placeholder?: string;
}>): JSX.Element {
  const [focused, setFocused] = useState(false);
  const numeric = Number.parseFloat(value);
  const display =
    !focused && value !== '' && Number.isFinite(numeric)
      ? formatAmount(numeric, currency)
      : value;
  return (
    <Input
      id={id}
      type="text"
      inputMode="decimal"
      placeholder={placeholder}
      value={display}
      onChange={(e) => onChange(sanitizeAmount(e.target.value))}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    />
  );
}

function HeaderActions({
  currentStatus,
  isPending,
  onMarkFinished,
  onReopen,
}: Readonly<{
  currentStatus: string;
  isPending: boolean;
  onMarkFinished: () => void;
  onReopen: () => void;
}>): JSX.Element | null {
  if (currentStatus === 'finished') {
    return (
      <Button
        type="button"
        variant="ghost"
        onClick={onReopen}
        disabled={isPending}
        className="border border-input"
      >
        <RotateCcw className="w-4 h-4 mr-2 text-score-green" />
        {isPending ? 'Updating...' : 'Reopen Project'}
      </Button>
    );
  }
  return (
    <Button
      type="button"
      variant="ghost"
      onClick={onMarkFinished}
      disabled={isPending}
      className="border border-input"
    >
      <CheckCircle className="w-4 h-4 mr-2 text-score-green" />
      {isPending ? 'Updating...' : 'Mark as Finished'}
    </Button>
  );
}

function ProgramField({
  control,
  programs,
  errorMessage,
  isCreating,
  onCreateProgram,
}: Readonly<{
  control: Control<ProjectFormData>;
  programs: ProgramSummary[];
  errorMessage?: string;
  isCreating: boolean;
  onCreateProgram: (name: string) => Promise<void>;
}>): JSX.Element {
  const [open, setOpen] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');

  const closeNew = (): void => {
    setShowNew(false);
    setNewName('');
  };

  return (
    <div>
      <div className="space-y-2 min-w-0">
        <TooltipProvider>
          <div className="h-5 flex items-center gap-2">
            <Label htmlFor="program_id">Program *</Label>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-muted-foreground hover:text-foreground transition-colors">
                  <Info className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs">
                <p className="text-sm">Every project belongs to a program. Pick an existing one or create a new program for this project.</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </TooltipProvider>
        <div className="flex gap-3 items-start min-w-0">
          <Controller
            name="program_id"
            control={control}
            rules={{ required: 'Program is required' }}
            render={({ field }) => (
              <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                  <Button
                    id="program_id"
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="flex-1 min-w-0 justify-between font-normal"
                  >
                    <span className="truncate">
                      {field.value
                        ? programs.find((p) => p.id === field.value)?.name ?? 'Unknown'
                        : 'Select a program…'}
                    </span>
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search programs..." />
                    <CommandList>
                      <CommandEmpty>No program found.</CommandEmpty>
                      <CommandGroup>
                        {programs.map((program) => (
                          <CommandItem
                            key={program.id}
                            value={program.name}
                            onSelect={() => {
                              field.onChange(program.id);
                              setOpen(false);
                            }}
                          >
                            <Check className={cn('mr-2 h-4 w-4', field.value === program.id ? 'opacity-100' : 'opacity-0')} />
                            <span className="truncate">{program.name}</span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            )}
          />
          {!showNew && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowNew(true)}
              className="shrink-0 text-muted-foreground hover:text-foreground"
            >
              <Plus className="w-4 h-4 mr-1" />
              New
            </Button>
          )}
        </div>
        {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
        {showNew && (
          <div className="flex gap-2 items-center">
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Program name"
              className="flex-1"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Escape') closeNew();
              }}
            />
            <Button
              type="button"
              size="sm"
              disabled={!newName.trim() || isCreating}
              onClick={async () => {
                await onCreateProgram(newName.trim());
                closeNew();
              }}
            >
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={closeNew}>
              Cancel
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProjectForm(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { setGuard } = useNavigationGuard();
  const isEditMode = !!id;

  const { data: project, isLoading: isLoadingProject, isError: isProjectError } =
    useProject(id ?? '');
  const { data: programsData } = usePrograms();
  const programs: ProgramSummary[] = useMemo(
    () => [...(programsData ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
    [programsData],
  );
  const createProgramMutation = useCreateProgram();
  const { data: currentMetrics } = useCurrentPeriodMetrics(id ?? '');

  const createMutation = useCreateProject();
  const replaceMutation = useReplaceProject(id ?? '');
  const deleteMutation = useDeleteProject();
  const statusMutation = useUpdateProjectStatus(id ?? '');
  const budgetMutation = useUpdateProjectBudget(id ?? '');
  const { data: existingBudgetLines } = useBudgetLines(id ?? '');
  const budgetLinesMutation = useReplaceBudgetLines(id ?? '');
  const { data: projectSettings } = useProjectSettings(id ?? '');
  const settingsMutation = useUpdateProjectSettings(id ?? '');

  const { data: dbCurrencies } = useQuery({
    queryKey: queryKeys.currencies.all,
    queryFn: () => trackerApi.listCurrencies(),
    staleTime: 300_000,
  });
  const currencyOptions = useMemo(
    () => buildCurrencyOptions(dbCurrencies ?? []),
    [dbCurrencies],
  );

  const {
    channels,
    isLoading: isLoadingChannels,
    isSlackConfigured,
    isCheckingStatus,
  } = useSlackChannels();

  const { data: users } = useUserSummaries();
  const activeUsersSorted = useMemo(
    () => (users ?? [])
      .sort((a, b) => getFullName(a.first_name, a.last_name).localeCompare(getFullName(b.first_name, b.last_name))),
    [users],
  );

  const [slackChannelId, setSlackChannelId] = useState<string>('');
  const [isBillable, setIsBillable] = useState<boolean>(true);
  const [hasScorecard, setHasScorecard] = useState<boolean>(true);
  const [hasDependabotAlerts, setHasDependabotAlerts] = useState<boolean>(true);
  const [hasBudgetAlerts, setHasBudgetAlerts] = useState<boolean>(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [proposalDialogOpen, setProposalDialogOpen] = useState(false);
  const [pendingSubmitData, setPendingSubmitData] = useState<ProjectFormData | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [formInitialized, setFormInitialized] = useState(false);
  const [pendingBudgetLines, setPendingBudgetLines] = useState<BudgetLineCreate[]>([]);

  const {
    register,
    handleSubmit,
    watch,
    reset,
    control,
    setValue,
    formState: { errors, isDirty },
  } = useForm<ProjectFormData>({
    defaultValues: {
      name: '',
      code: '',
      // New projects start as proposal (integration fields may stay blank);
      // the live gate kicks in when the status is switched.
      status: 'proposal',
      currency: 'dollar',
      program_id: '',
      project_manager_id: '',
      client_id: '',
      jira_project_key: '',
      github_repo: '',
      start_date: '',
      end_date: '',
      notes: '',
      summary: '',
      original_budget: '',
      contract_rate: '175',
      milestones: [{ ...EMPTY_MILESTONE }],
      links: [{ ...EMPTY_LINK }],
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
          : [{ ...EMPTY_LINK }],
      );
    }).catch(() => {
      setInitialLinks([{ ...EMPTY_LINK }]);
    });
  }, [isEditMode, id, linksRequested]);

  const linksReady = !isEditMode || initialLinks !== null;

  const settingsReady = !isEditMode || projectSettings !== undefined;

  useEffect(() => {
    if (!isEditMode || !project || formInitialized) return;
    if (currentMetrics === undefined || !linksReady || !settingsReady) return;
    reset(buildFormDefaults(project, currentMetrics?.milestones, initialLinks, projectSettings?.contract_rate));
    setSlackChannelId(project.slack_channel_id ?? '');
    setIsBillable(project.is_billable);
    setHasScorecard(project.has_scorecard);
    setHasDependabotAlerts(project.has_dependabot_alerts);
    setHasBudgetAlerts(project.has_budget_alerts);
    setFormInitialized(true);
  }, [isEditMode, project, formInitialized, currentMetrics, linksReady, settingsReady, initialLinks, projectSettings, reset]);

  const startDate = watch('start_date');
  const originalBudget = watch('original_budget');
  const currency = watch('currency');
  const budgetPreview = useBudgetPreview({
    originalBudget: originalBudget ?? '',
    currency: currency ?? '',
    startDate: startDate ?? '',
  });
  const { previewEur, noRate } = deriveBudgetPreviewState(
    budgetPreview,
    originalBudget ?? '',
    currency ?? '',
    startDate ?? '',
  );
  const currentStatus = watch('status');
  const currentManagerId = watch('project_manager_id');
  const [pmOpen, setPmOpen] = useState(false);
  const [clientOpen, setClientOpen] = useState(false);
  const currentClientId = watch('client_id');
  const { data: clientOptions = [] } = useClientOptions();

  const isMutating = createMutation.isPending || replaceMutation.isPending || budgetMutation.isPending || budgetLinesMutation.isPending || settingsMutation.isPending;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [extraDirty, setExtraDirty] = useState(false);
  const hasUnsavedChanges = (isDirty || extraDirty) && !isSubmitting;

  const guardFn = useCallback(
    () => !hasUnsavedChanges || window.confirm('You have unsaved changes. Leave this page?'),
    [hasUnsavedChanges],
  );

  useEffect(() => {
    setGuard(guardFn);
    return () => setGuard(null);
  }, [guardFn, setGuard]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e: BeforeUnloadEvent): void => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);

  const navigateToProjects = (): void => {
    navigate('/projects');
  };

  const handleLeave = (): void => {
    if (hasUnsavedChanges) {
      setLeaveDialogOpen(true);
    } else {
      navigateToProjects();
    }
  };

  // Integration requirements only bind live projects; proposals may stay blank.
  const isLive = currentStatus === 'live';
  const needsSlackChannel = isLive && hasDependabotAlerts && !slackChannelId;

  const handleFormSubmit = (data: ProjectFormData): void => {
    setApiError(null);

    if (needsSlackChannel) {
      setApiError('A Slack channel is required when a live project has Dependabot Alerts enabled.');
      return;
    }

    if (noRate) {
      setApiError('No exchange rate is available for this currency and start date; budget cannot be derived.');
      return;
    }

    if (data.status === 'proposal') {
      setPendingSubmitData(data);
      setProposalDialogOpen(true);
      return;
    }

    submitForm(data);
  };

  const buildPayloads = (data: ProjectFormData): {
    project: ProjectCreate;
    milestones: { milestones: { name: string; planned_date: string; actual_date?: string }[] } | null;
    links: { title: string; url: string; link_type: string }[];
    contractRate: number | null;
  } => {
    const project: ProjectCreate = {
      name: data.name,
      code: data.code,
      status: data.status,
      is_billable: isBillable,
      has_scorecard: hasScorecard,
      has_dependabot_alerts: hasDependabotAlerts,
      has_budget_alerts: hasBudgetAlerts,
      currency: data.currency,
      original_budget: data.original_budget ? Number.parseFloat(data.original_budget) : null,
      program_id: data.program_id || null,
      project_manager_id: data.project_manager_id || null,
      client_id: data.client_id || null,
      jira_project_key: data.jira_project_key || undefined,
      github_repo: data.github_repo || undefined,
      slack_channel_id: slackChannelId || undefined,
      start_date: data.start_date?.trim() || undefined,
      end_date: data.end_date?.trim() || undefined,
      notes: data.notes?.trim() || null,
      summary: data.summary?.trim() || null,
    };

    const validMilestones = data.milestones
      .filter((m) => m.name && m.planned_date)
      .map((m) => ({ name: m.name, planned_date: m.planned_date, actual_date: m.actual_date || undefined }));

    const contractRate = data.contract_rate ? Number.parseFloat(data.contract_rate) : null;

    return {
      project,
      milestones: validMilestones.length > 0 ? { milestones: validMilestones } : null,
      links: data.links.filter((l) => l.title || l.url),
      contractRate,
    };
  };

  const submitEdit = async (payloads: ReturnType<typeof buildPayloads>): Promise<void> => {
    const promises: Promise<unknown>[] = [replaceMutation.mutateAsync(payloads.project)];
    if (payloads.milestones) promises.push(budgetMutation.mutateAsync(payloads.milestones));
    promises.push(projectsApi.replaceLinks(id!, payloads.links));
    if (pendingBudgetLines.length > 0) promises.push(budgetLinesMutation.mutateAsync(pendingBudgetLines));
    if (payloads.contractRate && payloads.contractRate > 0) {
      promises.push(settingsMutation.mutateAsync({ contract_rate: payloads.contractRate }));
    }
    await Promise.all(promises);
  };

  const submitCreate = async (payloads: ReturnType<typeof buildPayloads>): Promise<void> => {
    const newProject = await createMutation.mutateAsync(payloads.project);
    if (!newProject?.id) return;
    const extras: Promise<unknown>[] = [];
    if (payloads.milestones) extras.push(projectsApi.updateBudget(newProject.id, payloads.milestones));
    if (payloads.links.length > 0) extras.push(projectsApi.replaceLinks(newProject.id, payloads.links));
    if (pendingBudgetLines.length > 0) extras.push(trackerApi.replaceBudgetLines(newProject.id, pendingBudgetLines));
    if (payloads.contractRate && payloads.contractRate > 0) {
      extras.push(trackerApi.updateProjectSettings(newProject.id, { contract_rate: payloads.contractRate }));
    }
    if (extras.length > 0) await Promise.all(extras);
  };

  const submitForm = async (data: ProjectFormData): Promise<void> => {
    setApiError(null);
    const payloads = buildPayloads(data);
    try {
      if (isEditMode) {
        await submitEdit(payloads);
      } else {
        await submitCreate(payloads);
      }
      setIsSubmitting(true);
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
        setIsSubmitting(true);
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
        onSuccess: () => setValue('status', 'finished', { shouldDirty: false }),
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
        onSuccess: () => setValue('status', 'live', { shouldDirty: false }),
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
            <HeaderActions
              currentStatus={currentStatus}
              isPending={statusMutation.isPending}
              onMarkFinished={handleMarkFinished}
              onReopen={handleReopen}
            />
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
                  {/* Row 1: Name, Code */}
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

                  {/* Row 2: Program */}
                  <ProgramField
                    control={control}
                    programs={programs}
                    errorMessage={errors.program_id?.message}
                    isCreating={createProgramMutation.isPending}
                    onCreateProgram={async (name) => {
                      const created = await createProgramMutation.mutateAsync(name);
                      setValue('program_id', created.id, { shouldValidate: true, shouldDirty: true });
                    }}
                  />

                  {/* Row 3: Project Manager, Status */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="project_manager_id" className="h-5 flex items-center">Project Manager</Label>
                      <Popover open={pmOpen} onOpenChange={setPmOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            id="project_manager_id"
                            variant="outline"
                            role="combobox"
                            aria-expanded={pmOpen}
                            className="w-full justify-between font-normal"
                          >
                            <span className="truncate">
                              {currentManagerId
                                ? getFullName(
                                    activeUsersSorted.find((u) => u.id === currentManagerId)?.first_name,
                                    activeUsersSorted.find((u) => u.id === currentManagerId)?.last_name,
                                    activeUsersSorted.find((u) => u.id === currentManagerId)?.email,
                                  )
                                : 'None'}
                            </span>
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                          <Command>
                            <CommandInput placeholder="Search users..." />
                            <CommandList>
                              <CommandEmpty>No user found.</CommandEmpty>
                              <CommandGroup>
                                <CommandItem
                                  value="__none__"
                                  onSelect={() => {
                                    setValue('project_manager_id', '');
                                    setPmOpen(false);
                                  }}
                                >
                                  <Check className={cn('mr-2 h-4 w-4', !currentManagerId ? 'opacity-100' : 'opacity-0')} />
                                  <span className="text-muted-foreground">None</span>
                                </CommandItem>
                                {activeUsersSorted.map((u) => (
                                  <CommandItem
                                    key={u.id}
                                    value={getFullName(u.first_name, u.last_name, u.email)}
                                    onSelect={() => {
                                      setValue('project_manager_id', u.id);
                                      setPmOpen(false);
                                    }}
                                  >
                                    <Check className={cn('mr-2 h-4 w-4', currentManagerId === u.id ? 'opacity-100' : 'opacity-0')} />
                                    {getFullName(u.first_name, u.last_name, u.email)}
                                  </CommandItem>
                                ))}
                              </CommandGroup>
                            </CommandList>
                          </Command>
                        </PopoverContent>
                      </Popover>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="status" className="h-5 flex items-center">Status</Label>
                      <NativeSelect id="status" className="w-full" {...register('status')}>
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </NativeSelect>
                    </div>
                  </div>

                  {/* Row: Client */}
                  <div className="space-y-2">
                    <Label htmlFor="client_id" className="h-5 flex items-center">Client</Label>
                    <Popover open={clientOpen} onOpenChange={setClientOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          id="client_id"
                          variant="outline"
                          role="combobox"
                          aria-expanded={clientOpen}
                          className="w-full justify-between font-normal"
                        >
                          <span className="truncate">
                            {currentClientId
                              ? clientOptions.find((c) => c.id === currentClientId)?.name ?? 'Unknown'
                              : 'None'}
                          </span>
                          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Search clients..." />
                          <CommandList>
                            <CommandEmpty>No client found.</CommandEmpty>
                            <CommandGroup>
                              <CommandItem
                                value="__none__"
                                onSelect={() => {
                                  setValue('client_id', '');
                                  setClientOpen(false);
                                }}
                              >
                                <Check className={cn('mr-2 h-4 w-4', !currentClientId ? 'opacity-100' : 'opacity-0')} />
                                <span className="text-muted-foreground">None</span>
                              </CommandItem>
                              {clientOptions.map((c) => (
                                <CommandItem
                                  key={c.id}
                                  value={`${c.name} ${c.code ?? ''}`}
                                  onSelect={() => {
                                    setValue('client_id', c.id);
                                    setClientOpen(false);
                                  }}
                                >
                                  <Check className={cn('mr-2 h-4 w-4', currentClientId === c.id ? 'opacity-100' : 'opacity-0')} />
                                  <span className="truncate">{c.name}</span>
                                  {c.code ? <span className="ml-2 text-xs text-muted-foreground">{c.code}</span> : null}
                                </CommandItem>
                              ))}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>

                  {/* Row: Budget (original currency), Currency */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="original_budget" className="h-5 flex items-center">Budget in original currency *</Label>
                      <Controller
                        name="original_budget"
                        control={control}
                        rules={{
                          required: 'Budget is required',
                          validate: (v) => {
                            const n = Number.parseFloat(v);
                            return (Number.isFinite(n) && n >= 0) || 'Must be positive';
                          },
                        }}
                        render={({ field }) => (
                          <CurrencyAmountInput
                            id="original_budget"
                            currency={currency}
                            value={field.value ?? ''}
                            onChange={field.onChange}
                            placeholder="e.g., 100000"
                          />
                        )}
                      />
                      {errors.original_budget && (
                        <p className="text-sm text-destructive">{errors.original_budget.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="currency" className="h-5 flex items-center">Currency *</Label>
                      <NativeSelect id="currency" className="w-full" {...register('currency', { required: true })}>
                        {currencyOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </NativeSelect>
                    </div>
                  </div>

                  {/* Row: Budget (EUR, derived read-only), Contract Rate */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="budget_eur" className="h-5 flex items-center">Budget (EUR)</Label>
                      <Input
                        id="budget_eur"
                        type="text"
                        readOnly
                        tabIndex={-1}
                        className="bg-muted"
                        value={formatBudgetEur(budgetPreview.isLoading, previewEur)}
                      />
                      {noRate && (
                        <p className="text-sm text-destructive">No exchange rate for this currency / start date.</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="contract_rate" className="h-5 flex items-center">Contract Rate (EUR)</Label>
                      <Input
                        id="contract_rate"
                        type="number"
                        step="0.01"
                        min="0.01"
                        placeholder="175.00"
                        {...register('contract_rate', {
                          min: { value: 0.01, message: 'Must be positive' },
                        })}
                      />
                      {errors.contract_rate && (
                        <p className="text-sm text-destructive">{errors.contract_rate.message}</p>
                      )}
                    </div>
                  </div>

                  {/* Row: Start Date, End Date */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="start_date" className="h-5 flex items-center">Start Date *</Label>
                      <Input
                        id="start_date"
                        type="date"
                        min={DATE_INPUT_MIN}
                        max={DATE_INPUT_MAX}
                        {...register('start_date', {
                          required: 'Start date is required',
                          pattern: { value: /^\d{4}-\d{2}-\d{2}$/, message: 'Invalid date format' },
                        })}
                      />
                      {errors.start_date && (
                        <p className="text-sm text-destructive">{errors.start_date.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="end_date" className="h-5 flex items-center">End Date *</Label>
                      <Input
                        id="end_date"
                        type="date"
                        min={DATE_INPUT_MIN}
                        max={DATE_INPUT_MAX}
                        {...register('end_date', {
                          required: 'End date is required',
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
                      <Label htmlFor="jira_project_key" className="h-5 flex items-center">
                        Jira Project Key{isLive && hasScorecard ? ' *' : ''}
                      </Label>
                      <Input
                        id="jira_project_key"
                        type="text"
                        placeholder="e.g., PROJ"
                        {...register('jira_project_key', {
                          validate: (v) =>
                            !isLive ||
                            !hasScorecard ||
                            !!v.trim() ||
                            'Required when a live project has Scorecard enabled',
                        })}
                      />
                      {errors.jira_project_key && (
                        <p className="text-sm text-destructive">{errors.jira_project_key.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="github_repo" className="h-5 flex items-center">
                        GitHub Repository{isLive && hasDependabotAlerts ? ' *' : ''}
                      </Label>
                      <Input
                        id="github_repo"
                        type="text"
                        placeholder="e.g., owner/repo"
                        {...register('github_repo', {
                          pattern: { value: /^$|^[^/]+\/[^/]+$/, message: 'Format: owner/repo' },
                          validate: (v) =>
                            !isLive ||
                            !hasDependabotAlerts ||
                            !!v.trim() ||
                            'Required when a live project has Dependabot Alerts enabled',
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
                        onValueChange={(v) => { setSlackChannelId(v); setExtraDirty(true); }}
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

            {/* Budget Lines */}
            <BudgetLinesEditor
              initialData={existingBudgetLines}
              onLinesChange={setPendingBudgetLines}
            />

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
                    onClick={() => appendMilestone({ ...EMPTY_MILESTONE })}
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
                    onClick={() => appendLink({ ...EMPTY_LINK })}
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
                    <Switch id="is_billable" checked={isBillable} onCheckedChange={(v) => { setIsBillable(v); setExtraDirty(true); }} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_scorecard" className="cursor-pointer text-sm">Scorecard</Label>
                    <Switch id="has_scorecard" checked={hasScorecard} onCheckedChange={(v) => { setHasScorecard(v); setExtraDirty(true); }} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_dependabot_alerts" className="cursor-pointer text-sm">Dependabot Alerts</Label>
                    <Switch id="has_dependabot_alerts" checked={hasDependabotAlerts} onCheckedChange={(v) => { setHasDependabotAlerts(v); setExtraDirty(true); }} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="has_budget_alerts" className="cursor-pointer text-sm">Budget Alerts</Label>
                    <Switch id="has_budget_alerts" checked={hasBudgetAlerts} onCheckedChange={(v) => { setHasBudgetAlerts(v); setExtraDirty(true); }} />
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
                    disabled={isMutating || noRate}
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {isMutating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                    {getSubmitButtonText(isMutating, isEditMode)}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={handleLeave}
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
                        className="w-full border border-input"
                      >
                        <Trash2 className="w-4 h-4 mr-2 text-destructive" />
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

      <AlertDialog open={leaveDialogOpen} onOpenChange={setLeaveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Are you sure you want to leave this page?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Stay on Page</AlertDialogCancel>
            <AlertDialogAction onClick={navigateToProjects}>
              Leave Page
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
