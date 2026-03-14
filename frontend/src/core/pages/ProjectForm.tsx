import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
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
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { ErrorBanner } from '@/shared/components/ui/error-banner';
import {
  Trash2,
  CheckCircle,
  RotateCcw,
  Lock,
  Loader2,
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

  const createMutation = useCreateProject();
  const replaceMutation = useReplaceProject(id ?? '');
  const deleteMutation = useDeleteProject();
  const statusMutation = useUpdateProjectStatus(id ?? '');

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
    },
  });

  if (isEditMode && project && !formInitialized) {
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

  const isMutating = createMutation.isPending || replaceMutation.isPending;

  const navigateToProjects = (): void => {
    navigate('/projects');
  };

  const handleFormSubmit = (data: ProjectFormData): void => {
    setApiError(null);

    const payload: ProjectCreate = {
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

    if (isEditMode) {
      replaceMutation.mutate(payload, {
        onSuccess: navigateToProjects,
        onError: (error) => setApiError(getApiErrorMessage(error)),
      });
    } else {
      createMutation.mutate(payload, {
        onSuccess: navigateToProjects,
        onError: (error) => setApiError(getApiErrorMessage(error)),
      });
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
