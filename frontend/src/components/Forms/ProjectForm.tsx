import { useForm } from 'react-hook-form';
import type { Project, ProjectCreate } from '../../types';

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
      <div>
        <label htmlFor="name" className="label">
          Project Name *
        </label>
        <input
          id="name"
          type="text"
          className="input"
          {...register('name', { required: 'Project name is required' })}
        />
        {errors.name && (
          <p className="text-sm text-red-500 mt-1">{errors.name.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="jira_project_key" className="label">
          Jira Project Key
        </label>
        <input
          id="jira_project_key"
          type="text"
          className="input"
          placeholder="e.g., PROJ"
          {...register('jira_project_key')}
        />
      </div>

      <div>
        <label htmlFor="github_repo" className="label">
          GitHub Repository
        </label>
        <input
          id="github_repo"
          type="text"
          className="input"
          placeholder="e.g., owner/repo"
          {...register('github_repo', {
            pattern: {
              value: /^$|^[^/]+\/[^/]+$/,
              message: 'Format: owner/repo',
            },
          })}
        />
        {errors.github_repo && (
          <p className="text-sm text-red-500 mt-1">{errors.github_repo.message}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="start_date" className="label">
            Start Date
          </label>
          <input
            id="start_date"
            type="date"
            className="input"
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
            <p className="text-sm text-red-500 mt-1">{errors.start_date.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="end_date" className="label">
            End Date
          </label>
          <input
            id="end_date"
            type="date"
            className="input"
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
            <p className="text-sm text-red-500 mt-1">{errors.end_date.message}</p>
          )}
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="btn-secondary"
          disabled={isLoading}
        >
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={isLoading}>
          {getSubmitButtonText(isLoading, isEditMode)}
        </button>
      </div>
    </form>
  );
}
