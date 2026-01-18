import { useForm } from 'react-hook-form';
import type { ProjectCreate } from '../../types';

interface CreateProjectFormProps {
  onSubmit: (data: ProjectCreate) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function CreateProjectForm({
  onSubmit,
  onCancel,
  isLoading = false,
}: CreateProjectFormProps): JSX.Element {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProjectCreate>();

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
          placeholder="e.g., org/repo"
          {...register('github_repo', {
            pattern: {
              value: /^[^/]+\/[^/]+$/,
              message: 'Format: owner/repo',
            },
          })}
        />
        {errors.github_repo && (
          <p className="text-sm text-red-500 mt-1">{errors.github_repo.message}</p>
        )}
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
          {isLoading ? 'Creating...' : 'Create Project'}
        </button>
      </div>
    </form>
  );
}
