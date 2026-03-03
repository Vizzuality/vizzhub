import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProjectForm from './ProjectForm';
import type { Project, SlackChannel } from '../../types';

vi.mock('@/core/hooks/useSlackChannels', () => ({
  useSlackChannels: vi.fn(),
}));

import { useSlackChannels } from '@/core/hooks/useSlackChannels';

const mockUseSlackChannels = vi.mocked(useSlackChannels);

const mockSlackChannels: SlackChannel[] = [
  { id: 'C123', name: 'general', is_private: false },
  { id: 'C456', name: 'engineering', is_private: false },
  { id: 'C789', name: 'private-channel', is_private: true },
];

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
    mockUseSlackChannels.mockReturnValue({
      channels: mockSlackChannels,
      isLoading: false,
      isError: false,
      error: null,
      isSlackConfigured: true,
      isCheckingStatus: false,
    });
  });

  describe('Rendering', () => {
    it('renders all form fields', () => {
      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/jira project key/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/github repository/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/slack channel/i)).toBeInTheDocument();
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
        slack_channel_id: null,
        start_date: null,
        end_date: null,
        status: 'in_progress',
        finished_at: null,
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
        slack_channel_id: null,
        start_date: null,
        end_date: null,
        status: 'in_progress',
        finished_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} isLoading={true} />);

      expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
    });
  });

  describe('Slack Channel Field', () => {
    it('shows Slack channel dropdown when configured', () => {
      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByLabelText(/slack channel/i)).toBeInTheDocument();
      expect(screen.getByText(/select a channel to receive/i)).toBeInTheDocument();
    });

    it('shows message when Slack is not configured', () => {
      mockUseSlackChannels.mockReturnValue({
        channels: [],
        isLoading: false,
        isError: false,
        error: null,
        isSlackConfigured: false,
        isCheckingStatus: false,
      });

      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByText(/slack is not configured/i)).toBeInTheDocument();
    });

    it('shows loading state while checking Slack status', () => {
      mockUseSlackChannels.mockReturnValue({
        channels: [],
        isLoading: false,
        isError: false,
        error: null,
        isSlackConfigured: false,
        isCheckingStatus: true,
      });

      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByText(/checking slack configuration/i)).toBeInTheDocument();
    });

    it('shows loading state while loading channels', async () => {
      mockUseSlackChannels.mockReturnValue({
        channels: [],
        isLoading: true,
        isError: false,
        error: null,
        isSlackConfigured: true,
        isCheckingStatus: false,
      });

      render(<ProjectForm {...defaultProps} />);

      expect(screen.getByText(/loading channels/i)).toBeInTheDocument();
    });

    it('populates with existing slack channel in edit mode', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Test Project',
        jira_project_key: null,
        github_repo: null,
        slack_channel_id: 'C456',
        start_date: null,
        end_date: null,
        status: 'in_progress',
        finished_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      const combobox = screen.getByRole('combobox');
      expect(combobox).toHaveTextContent('#engineering');
    });

    it('submits form without slack channel when none selected', async () => {
      const user = userEvent.setup();
      render(<ProjectForm {...defaultProps} />);

      await user.type(screen.getByLabelText(/project name/i), 'My Project');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'My Project',
            slack_channel_id: undefined,
          })
        );
      });
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
          slack_channel_id: undefined,
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
          slack_channel_id: undefined,
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
            slack_channel_id: undefined,
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
    it('populates form with existing project data including slack channel', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Existing Project',
        jira_project_key: 'EXIST',
        github_repo: 'org/existing',
        slack_channel_id: 'C123',
        start_date: '2026-03-01',
        end_date: '2026-09-30',
        status: 'in_progress',
        finished_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      };

      render(<ProjectForm {...defaultProps} project={existingProject} />);

      expect(screen.getByLabelText(/project name/i)).toHaveValue('Existing Project');
      expect(screen.getByLabelText(/jira project key/i)).toHaveValue('EXIST');
      expect(screen.getByLabelText(/github repository/i)).toHaveValue('org/existing');
      const combobox = screen.getByRole('combobox');
      expect(combobox).toHaveTextContent('#general');
      expect(screen.getByLabelText(/start date/i)).toHaveValue('2026-03-01');
      expect(screen.getByLabelText(/end date/i)).toHaveValue('2026-09-30');
    });

    it('handles null optional fields in existing project', () => {
      const existingProject: Project = {
        id: '123',
        name: 'Minimal Project',
        jira_project_key: null,
        github_repo: null,
        slack_channel_id: null,
        start_date: null,
        end_date: null,
        status: 'in_progress',
        finished_at: null,
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
        slack_channel_id: null,
        start_date: null,
        end_date: null,
        status: 'in_progress',
        finished_at: null,
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
