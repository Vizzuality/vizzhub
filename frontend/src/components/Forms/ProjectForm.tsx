import { useForm } from 'react-hook-form';
import type { Project, ProjectCreate } from '../../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function getSubmitButtonText(isLoading: boolean, isEditMode: boolean): string {
  if (isLoading) {
    return isEditMode ? 'Saving...' : 'Creating...';
  }
  return isEditMode ? 'Save Changes' : 'Create Project';
}

interface ProjectFormData {
  name: string;
  jira_project_key: string;
  github_repo: string;
  start_date: string;
  end_date: string;
}

interface ProjectFormProps {
  project?: Project;
  onSubmit: (data: ProjectCreate) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function ProjectForm({
  project,
  onSubmit,
  onCancel,
  isLoading = false,
}: ProjectFormProps): JSX.Element {
  const isEditMode = !!project;

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ProjectFormData>({
    defaultValues: {
      name: project?.name ?? '',
      jira_project_key: project?.jira_project_key ?? '',
      github_repo: project?.github_repo ?? '',
      start_date: project?.start_date ?? '',
      end_date: project?.end_date ?? '',
    },
  });

  const startDate = watch('start_date');

  const handleFormSubmit = (data: ProjectFormData): void => {
    const payload: ProjectCreate = {
      name: data.name,
      jira_project_key: data.jira_project_key || undefined,
      github_repo: data.github_repo || undefined,
      start_date: data.start_date && data.start_date.trim() !== '' ? data.start_date : undefined,
      end_date: data.end_date && data.end_date.trim() !== '' ? data.end_date : undefined,
    };
    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">
          Project Name *
        </Label>
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
        <Label htmlFor="jira_project_key">
          Jira Project Key
        </Label>
        <Input
          id="jira_project_key"
          type="text"
          placeholder="e.g., PROJ"
          {...register('jira_project_key')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="github_repo">
          GitHub Repository
        </Label>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="start_date">
            Start Date
          </Label>
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
          <Label htmlFor="end_date">
            End Date
          </Label>
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
                  new Date(value) > new Date(startDate) ||
                  'End date must be after start date'
                );
              },
            })}
          />
          {errors.end_date && (
            <p className="text-sm text-destructive">{errors.end_date.message}</p>
          )}
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          disabled={isLoading}
          className="border border-input"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={isLoading}
          className="bg-primary text-primary-foreground hover:bg-primary/90"
        >
          {getSubmitButtonText(isLoading, isEditMode)}
        </Button>
      </div>
    </form>
  );
}
