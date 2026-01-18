import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProjectForm from './ProjectForm';
import type { Project } from '../../types';

describe('ProjectForm', () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  const defaultProps = {
    onSubmit: mockOnSubmit,
    onCancel: mockOnCancel,
    isLoading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders all form fields', () => {
      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/jira project key/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/github repository/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create project/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('shows Create Project button text in create mode', () => {
      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: /create project/i })).toBeInTheDocument();
    });

    it('shows Save Changes button text in edit mode', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Test Project',
        jira_project_key: null,
        github_repo: null,
        start_date: null,
        end_date: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });

    it('shows loading state when isLoading is true', () => {
      render(<ProjectForm {...defaultProps} isLoading={true} />);

      expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('shows Saving text when loading in edit mode', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Test Project',
        jira_project_key: null,
        github_repo: null,
        start_date: null,
        end_date: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} isLoading={true} />);

      expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
    });
  });

  describe('Validation', () => {
    it('shows validation error when name is empty on submit', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(screen.getByText(/project name is required/i)).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('shows validation error for invalid github repo format', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test Project');
      await user.type(screen.getByLabelText(/github repository/i), 'invalid-format');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(screen.getByText(/format: owner\/repo/i)).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('validates end date is after start date', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test Project');
      await user.type(screen.getByLabelText(/start date/i), '2026-12-31');
      await user.type(screen.getByLabelText(/end date/i), '2026-01-01');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(screen.getByText(/end date must be after start date/i)).toBeInTheDocument();
      });
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('allows empty github repo field', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test Project');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });
    });

    it('accepts valid github repo format', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test Project');
      await user.type(screen.getByLabelText(/github repository/i), 'owner/repo');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });
      expect(screen.queryByText(/format: owner\/repo/i)).not.toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('submits form with valid data', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'My Project');
      await user.type(screen.getByLabelText(/jira project key/i), 'PROJ');
      await user.type(screen.getByLabelText(/github repository/i), 'org/repo');
      await user.type(screen.getByLabelText(/start date/i), '2026-01-01');
      await user.type(screen.getByLabelText(/end date/i), '2026-12-31');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith({
          name: 'My Project',
          jira_project_key: 'PROJ',
          github_repo: 'org/repo',
          start_date: '2026-01-01',
          end_date: '2026-12-31',
        });
      });
    });

    it('submits form with minimal data (only name)', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Minimal Project');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith({
          name: 'Minimal Project',
          jira_project_key: undefined,
          github_repo: undefined,
          start_date: undefined,
          end_date: undefined,
        });
      });
    });

    it('converts empty optional fields to undefined', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            jira_project_key: undefined,
            github_repo: undefined,
          })
        );
      });
    });
  });

  describe('Cancel Action', () => {
    it('calls onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(mockOnCancel).toHaveBeenCalled();
    });

    it('does not submit form when cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'Test');
      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Edit Mode', () => {
    it('populates form with existing project data', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Existing Project',
        jira_project_key: 'EXIST',
        github_repo: 'org/existing',
        start_date: '2026-03-01',
        end_date: '2026-09-30',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      expect(screen.getByLabelText(/project name/i)).toHaveValue('Existing Project');
      expect(screen.getByLabelText(/jira project key/i)).toHaveValue('EXIST');
      expect(screen.getByLabelText(/github repository/i)).toHaveValue('org/existing');
      expect(screen.getByLabelText(/start date/i)).toHaveValue('2026-03-01');
      expect(screen.getByLabelText(/end date/i)).toHaveValue('2026-09-30');
    });

    it('handles null optional fields in existing project', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Minimal Project',
        jira_project_key: null,
        github_repo: null,
        start_date: null,
        end_date: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      expect(screen.getByLabelText(/project name/i)).toHaveValue('Minimal Project');
      expect(screen.getByLabelText(/jira project key/i)).toHaveValue('');
      expect(screen.getByLabelText(/github repository/i)).toHaveValue('');
      expect(screen.getByLabelText(/start date/i)).toHaveValue('');
      expect(screen.getByLabelText(/end date/i)).toHaveValue('');
    });

    it('submits updated data in edit mode', async () => {
      const user = userEvent.setup();
      const existingProject: Project = {
        id: '123',
        name: 'Old Name',
        jira_project_key: 'OLD',
        github_repo: null,
        start_date: null,
        end_date: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      const nameInput = screen.getByLabelText(/project name/i);
      await user.clear(nameInput);
      await user.type(nameInput, 'New Name');
      await user.click(screen.getByRole('button', { name: /save changes/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New Name',
          })
        );
      });
    });
  });
});
