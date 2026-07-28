import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { server } from '@/test/setup';
import ProjectForm from '../ProjectForm';

const BASE = '/api';

const slackDisconnected = {
  jira: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  google_workspace: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  github: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  slack: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  slack_settings: { leadership_channel_id: null },
};

const projectNoDependabot = {
  id: 'project-123',
  name: 'Test Project',
  code: 'TST.001',
  program_id: 'prog-1',
  program_name: 'Program Alpha',
  is_billable: true,
  has_scorecard: true,
  has_dependabot_alerts: false,
  has_budget_alerts: true,
  currency: 'euro',
  budget: 90000,
  original_budget: 100000,
  notes: null,
  summary: null,
  jira_project_key: 'TEST',
  github_repo: 'org/test-repo',
  slack_channel_id: null,
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  status: 'live' as const,
  finished_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
};

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderCreate(): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={['/projects/new']}>
        <Routes>
          <Route path="/projects/new" element={<ProjectForm />} />
          <Route path="/projects" element={<div data-testid="projects-list">Projects List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderEdit(projectId = 'project-123'): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/edit`]}>
        <Routes>
          <Route path="/projects/:id/edit" element={<ProjectForm />} />
          <Route path="/projects" element={<div data-testid="projects-list">Projects List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function selectProgram(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  // Program is mandatory; wait for the options request to settle before selecting.
  await waitFor(() => {
    const select = screen.getByLabelText(/program \*/i);
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toContain(
      'Program Alpha',
    );
  });
  await user.selectOptions(screen.getByLabelText(/program \*/i), 'prog-1');
}

async function fillRequiredFields(
  user: ReturnType<typeof userEvent.setup>,
  overrides: { name?: string; code?: string; budget?: string } = {},
): Promise<void> {
  await user.type(screen.getByLabelText(/name \*/i), overrides.name ?? 'Test Project');
  await user.type(screen.getByLabelText(/code \*/i), overrides.code ?? 'TST.001');
  await selectProgram(user);
  // Default status is live with Scorecard/Dependabot on → jira + github required.
  await user.type(screen.getByLabelText(/jira project key/i), 'TST');
  await user.type(screen.getByLabelText(/github repository/i), 'org/tst');
  await user.type(
    screen.getByLabelText(/Budget in original currency/i),
    overrides.budget ?? '50000',
  );
  fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: '2026-01-01' } });
  fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-12-31' } });
}

describe('ProjectForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  describe('Create Mode — Rendering', () => {
    it('renders with "New Project" heading', async () => {
      renderCreate();
      expect(await screen.findByText('New Project')).toBeInTheDocument();
    });

    it('renders all form sections', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.getByText('General')).toBeInTheDocument();
      expect(screen.getByText('Integrations')).toBeInTheDocument();
      expect(screen.getByText('Milestones')).toBeInTheDocument();
      expect(screen.getByText('Links')).toBeInTheDocument();
      expect(screen.getByText('Features')).toBeInTheDocument();
      expect(screen.getByText('Notes')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });

    it('renders required fields: name and code', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.getByLabelText(/name \*/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/code \*/i)).toBeInTheDocument();
    });

    it('renders "Create Project" submit button', async () => {
      renderCreate();
      expect(await screen.findByRole('button', { name: /create project/i })).toBeInTheDocument();
    });

    it('does not render delete button in create mode', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.queryByRole('button', { name: /delete project/i })).not.toBeInTheDocument();
    });

    it('renders cancel button', async () => {
      renderCreate();
      expect(await screen.findByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('renders feature toggles with default values', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.getByLabelText('Billable')).toBeInTheDocument();
      expect(screen.getByLabelText('Scorecard')).toBeInTheDocument();
      expect(screen.getByLabelText('Dependabot Alerts')).toBeInTheDocument();
      expect(screen.getByLabelText('Budget Alerts')).toBeInTheDocument();
    });

    it('renders currency dropdown with options', async () => {
      renderCreate();
      await screen.findByText('New Project');

      const currencySelect = screen.getByLabelText('Currency *');
      const options = within(currencySelect).getAllByRole('option');
      expect(options).toHaveLength(2);
      expect(options[0]).toHaveTextContent('US Dollar (USD)');
      expect(options[1]).toHaveTextContent('Euro (EUR)');
    });

    it('renders status dropdown with three options', async () => {
      renderCreate();
      await screen.findByText('New Project');

      const statusSelect = screen.getByLabelText(/status/i);
      const options = within(statusSelect).getAllByRole('option');
      expect(options).toHaveLength(3);
      expect(options.map((o) => o.textContent)).toEqual(['Proposal', 'Live', 'Finished']);
    });
  });

  describe('Create Mode — Validation', () => {
    it('shows error when name is empty', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('Project name is required')).toBeInTheDocument();
    });

    it('shows error when code is empty', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test Project');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('Project code is required')).toBeInTheDocument();
    });

    it('shows error for invalid GitHub repo format', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test');
      await user.type(screen.getByLabelText(/code \*/i), 'TST');
      await user.type(screen.getByLabelText(/github repository/i), 'invalid-format');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('Format: owner/repo')).toBeInTheDocument();
    });

    it('validates end date is after start date', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test');
      await user.type(screen.getByLabelText(/code \*/i), 'TST');
      const startInput = screen.getByLabelText(/start date/i);
      const endInput = screen.getByLabelText(/end date/i);
      await user.clear(startInput);
      await user.type(startInput, '2026-06-01');
      await user.clear(endInput);
      await user.type(endInput, '2026-01-01');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('End date must be on or after start date')).toBeInTheDocument();
    });

    it('requires Slack channel when Dependabot alerts are enabled', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await fillRequiredFields(user, { name: 'Test', code: 'TST' });

      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(
        await screen.findByText(
          /slack channel is required when a live project has dependabot alerts enabled/i,
        ),
      ).toBeInTheDocument();
    });

    it('requires a program before submitting', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test');
      await user.type(screen.getByLabelText(/code \*/i), 'TST');
      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('Program is required')).toBeInTheDocument();
    });

    it('requires jira and github for live projects with scorecard/dependabot enabled', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test');
      await user.type(screen.getByLabelText(/code \*/i), 'TST');
      await selectProgram(user);
      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(
        await screen.findByText(/required when a live project has scorecard enabled/i),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/required when a live project has dependabot alerts enabled/i),
      ).toBeInTheDocument();
    });

    it('allows blank jira/github when status is proposal', async () => {
      const user = userEvent.setup();

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
      );

      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Blank Proposal');
      await user.type(screen.getByLabelText(/code \*/i), 'BLK');
      await selectProgram(user);
      await user.type(screen.getByLabelText(/Budget in original currency/i), '50000');
      fireEvent.change(screen.getByLabelText(/start date/i), { target: { value: '2026-01-01' } });
      fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-12-31' } });
      await user.selectOptions(screen.getByLabelText(/status/i), 'proposal');

      await user.click(screen.getByRole('button', { name: /create project/i }));

      // No jira/github validation errors — flow reaches the proposal dialog
      expect(await screen.findByText('Save as Proposal?')).toBeInTheDocument();
      expect(
        screen.queryByText(/required when a live project/i),
      ).not.toBeInTheDocument();
    });
  });

  describe('Create Mode — Proposal Confirmation Dialog', () => {
    it('shows confirmation dialog when status is proposal', async () => {
      const user = userEvent.setup();

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
      );

      renderCreate();
      await screen.findByText('New Project');

      await fillRequiredFields(user, { name: 'Test Proposal', code: 'TST' });

      // Set status to proposal (default is live)
      await user.selectOptions(screen.getByLabelText(/status/i), 'proposal');

      // Turn off Dependabot to avoid Slack validation
      await user.click(screen.getByLabelText('Dependabot Alerts'));

      await user.click(screen.getByRole('button', { name: /create project/i }));

      expect(await screen.findByText('Save as Proposal?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /save as proposal/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /back to edit/i })).toBeInTheDocument();
    });

    it('dismisses proposal dialog on "Back to Edit"', async () => {
      const user = userEvent.setup();

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
      );

      renderCreate();
      await screen.findByText('New Project');

      await fillRequiredFields(user, { name: 'Test Proposal', code: 'TST' });
      await user.selectOptions(screen.getByLabelText(/status/i), 'proposal');
      await user.click(screen.getByLabelText('Dependabot Alerts'));

      await user.click(screen.getByRole('button', { name: /create project/i }));
      await screen.findByText('Save as Proposal?');

      await user.click(screen.getByRole('button', { name: /back to edit/i }));

      await waitFor(() => {
        expect(screen.queryByText('Save as Proposal?')).not.toBeInTheDocument();
      });
    });
  });

  describe('Create Mode — Successful Submission', () => {
    it('creates project and navigates to list on success', async () => {
      const user = userEvent.setup();
      let capturedPayload: Record<string, unknown> | null = null;

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
        http.post(`${BASE}/projects`, async ({ request }) => {
          capturedPayload = await request.json() as Record<string, unknown>;
          return HttpResponse.json(
            { id: 'new-id', ...capturedPayload, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
            { status: 201 },
          );
        }),
      );

      renderCreate();
      await screen.findByText('New Project');

      await fillRequiredFields(user, { name: 'New Test Project', code: 'NTP-001' });

      // Turn off Dependabot to skip Slack validation
      await user.click(screen.getByLabelText('Dependabot Alerts'));

      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        expect(screen.getByTestId('projects-list')).toBeInTheDocument();
      });

      expect(capturedPayload).not.toBeNull();
      expect(capturedPayload!.name).toBe('New Test Project');
      expect(capturedPayload!.code).toBe('NTP-001');
    });

    it('creates project via proposal confirmation dialog', async () => {
      const user = userEvent.setup();
      let capturedPayload: Record<string, unknown> | null = null;

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
        http.post(`${BASE}/projects`, async ({ request }) => {
          capturedPayload = await request.json() as Record<string, unknown>;
          return HttpResponse.json(
            { id: 'new-id', ...capturedPayload, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
            { status: 201 },
          );
        }),
      );

      renderCreate();
      await screen.findByText('New Project');

      await fillRequiredFields(user, { name: 'Proposal Project', code: 'PRP-001' });
      await user.selectOptions(screen.getByLabelText(/status/i), 'proposal');
      await user.click(screen.getByLabelText('Dependabot Alerts'));

      await user.click(screen.getByRole('button', { name: /create project/i }));
      await screen.findByText('Save as Proposal?');

      await user.click(screen.getByRole('button', { name: /save as proposal/i }));

      await waitFor(() => {
        expect(screen.getByTestId('projects-list')).toBeInTheDocument();
      });

      expect(capturedPayload!.status).toBe('proposal');
    });
  });

  describe('Create Mode — API Error Handling', () => {
    it('shows API error message when creation fails', async () => {
      const user = userEvent.setup();

      server.use(
        http.get(`${BASE}/admin/integrations/status`, () =>
          HttpResponse.json(slackDisconnected),
        ),
        http.post(`${BASE}/projects`, () => {
          return HttpResponse.json(
            { detail: 'Duplicate project code' },
            { status: 422 },
          );
        }),
      );

      renderCreate();
      await screen.findByText('New Project');

      await user.type(screen.getByLabelText(/name \*/i), 'Test');
      await user.type(screen.getByLabelText(/code \*/i), 'TST');

      await user.click(screen.getByLabelText('Dependabot Alerts'));

      await user.click(screen.getByRole('button', { name: /create project/i }));

      await waitFor(() => {
        const errorBanner = document.querySelector('.text-destructive');
        expect(errorBanner).toBeTruthy();
      });
    });
  });

  describe('Create Mode — Milestones', () => {
    it('renders empty milestone row by default', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.getByPlaceholderText('e.g., MVP Release')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add milestone/i })).toBeInTheDocument();
    });

    it('adds milestone rows', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.click(screen.getByRole('button', { name: /add milestone/i }));

      expect(screen.getAllByPlaceholderText('e.g., MVP Release')).toHaveLength(2);
    });
  });

  describe('Create Mode — Links', () => {
    it('renders empty link row by default', async () => {
      renderCreate();
      await screen.findByText('New Project');

      expect(screen.getByPlaceholderText('e.g., GitHub Repo')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('https://...')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add link/i })).toBeInTheDocument();
    });

    it('adds link rows', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      await user.click(screen.getByRole('button', { name: /add link/i }));

      expect(screen.getAllByPlaceholderText('e.g., GitHub Repo')).toHaveLength(2);
    });

    it('renders link type options', async () => {
      renderCreate();
      await screen.findByText('New Project');

      const linksSection = screen.getByText('Links').closest('section')!;
      const selects = within(linksSection).getAllByRole('combobox');
      expect(selects.length).toBeGreaterThanOrEqual(1);

      const options = within(selects[0]).getAllByRole('option');
      expect(options.map((o) => o.textContent)).toContain('Code');
      expect(options.map((o) => o.textContent)).toContain('Project Management');
      expect(options.map((o) => o.textContent)).toContain('App Environments');
      expect(options.map((o) => o.textContent)).toContain('Design');
    });
  });

  describe('Edit Mode — Rendering', () => {
    it('renders with "Edit Project" heading', async () => {
      renderEdit();
      expect(await screen.findByText('Edit Project')).toBeInTheDocument();
    });

    it('renders "Save Changes" submit button', async () => {
      renderEdit();
      expect(await screen.findByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });

    it('renders "Delete Project" button', async () => {
      renderEdit();
      expect(await screen.findByRole('button', { name: /delete project/i })).toBeInTheDocument();
    });

    it('renders "Mark as Finished" button for live projects', async () => {
      renderEdit();
      expect(await screen.findByRole('button', { name: /mark as finished/i })).toBeInTheDocument();
    });

    it('populates form with project data', async () => {
      renderEdit();
      await screen.findByText('Edit Project');

      await waitFor(() => {
        expect(screen.getByLabelText(/name \*/i)).toHaveValue('Test Project');
        expect(screen.getByLabelText(/code \*/i)).toHaveValue('TST.001');
      });
    });
  });

  describe('Edit Mode — Loading and Error States', () => {
    it('shows loading spinner while project loads', async () => {
      server.use(
        http.get(`${BASE}/projects/:id`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 5000));
          return HttpResponse.json({});
        }),
      );

      renderEdit();
      expect(document.querySelector('.animate-spin')).toBeTruthy();
    });

    it('shows error when project fails to load', async () => {
      server.use(
        http.get(`${BASE}/projects/:id`, () => {
          return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
        }),
      );

      renderEdit('nonexistent');

      expect(await screen.findByText(/failed to load project/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /back to projects/i })).toBeInTheDocument();
    });
  });

  describe('Edit Mode — Delete', () => {
    it('shows delete confirmation dialog', async () => {
      const user = userEvent.setup();
      renderEdit();
      await screen.findByText('Edit Project');

      await user.click(screen.getByRole('button', { name: /delete project/i }));

      expect(await screen.findByText(/this action cannot be undone/i)).toBeInTheDocument();
    });

    it('navigates to projects list after successful delete', async () => {
      const user = userEvent.setup();
      renderEdit();
      await screen.findByText('Edit Project');

      await user.click(screen.getByRole('button', { name: /delete project/i }));
      await screen.findByText(/this action cannot be undone/i);

      const dialogDeleteBtn = screen.getAllByRole('button').find(
        (btn) => btn.textContent?.trim() === 'Delete',
      );
      expect(dialogDeleteBtn).toBeDefined();
      await user.click(dialogDeleteBtn!);

      await waitFor(() => {
        expect(screen.getByTestId('projects-list')).toBeInTheDocument();
      });
    });

    it('shows error when delete fails (409 conflict)', async () => {
      const user = userEvent.setup();

      server.use(
        http.delete(`${BASE}/projects/:id`, () => {
          return HttpResponse.json(
            { detail: 'Cannot delete: project has 5 time report entries.' },
            { status: 409 },
          );
        }),
      );

      renderEdit();
      await screen.findByText('Edit Project');

      await user.click(screen.getByRole('button', { name: /delete project/i }));
      await screen.findByText(/this action cannot be undone/i);

      const dialogDeleteBtn = screen.getAllByRole('button').find(
        (btn) => btn.textContent?.trim() === 'Delete',
      );
      await user.click(dialogDeleteBtn!);

      await waitFor(() => {
        const errorBanner = document.querySelector('.border-destructive');
        expect(errorBanner).toBeTruthy();
      });
    });
  });

  describe('Edit Mode — Successful Update', () => {
    it('saves project and navigates to list', async () => {
      const user = userEvent.setup();
      let capturedPayload: Record<string, unknown> | null = null;

      server.use(
        http.get(`${BASE}/projects/budget-preview`, () => {
          return HttpResponse.json({ budget_eur: 90000 });
        }),
        http.get(`${BASE}/projects/:id`, () => {
          return HttpResponse.json(projectNoDependabot);
        }),
        http.get(`${BASE}/metrics/project/:projectId/:year/:month`, () => {
          return HttpResponse.json({
            id: 'metrics-1',
            project_id: 'project-123',
            period_year: 2026,
            period_month: 3,
            milestones: [],
          });
        }),
        http.put(`${BASE}/projects/project-123`, async ({ request }) => {
          capturedPayload = await request.json() as Record<string, unknown>;
          return HttpResponse.json({
            id: 'project-123',
            ...capturedPayload,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-15T00:00:00Z',
          });
        }),
        http.put(`${BASE}/projects/project-123/budget`, () => {
          return HttpResponse.json({ period_year: 2026, period_month: 3, milestones: [] });
        }),
        http.put(`${BASE}/projects/project-123/links`, () => {
          return HttpResponse.json([]);
        }),
        http.get(`${BASE}/tracker/projects/project-123/budget-lines`, () => {
          return HttpResponse.json([]);
        }),
        http.get(`${BASE}/functional-areas`, () => {
          return HttpResponse.json([]);
        }),
      );

      renderEdit();
      await screen.findByText('Edit Project');

      // Wait for form to fully initialize (project + metrics loaded)
      await waitFor(() => {
        expect(screen.getByLabelText(/name \*/i)).toHaveValue('Test Project');
      }, { timeout: 5000 });

      const nameInput = screen.getByLabelText(/name \*/i);
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Project');

      await user.click(screen.getByRole('button', { name: /save changes/i }));

      await waitFor(() => {
        expect(screen.getByTestId('projects-list')).toBeInTheDocument();
      }, { timeout: 5000 });

      expect(capturedPayload!.name).toBe('Updated Project');
      // Edit seam: the PUT carries original_budget (seeded from the project) and
      // never sends budget — the backend derives it.
      expect(capturedPayload!.original_budget).toBe(100000);
      expect(capturedPayload!).not.toHaveProperty('budget');
    });
  });

  describe('Edit Mode — Finished Projects', () => {
    it('shows "Reopen Project" button for finished projects', async () => {
      server.use(
        http.get(`${BASE}/projects/:id`, () => {
          return HttpResponse.json({
            ...projectNoDependabot,
            name: 'Finished Project',
            code: 'FIN.001',
            status: 'finished',
            finished_at: '2026-03-01',
          });
        }),
      );

      renderEdit();
      expect(await screen.findByRole('button', { name: /reopen project/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /mark as finished/i })).not.toBeInTheDocument();
    });
  });

  describe('Create Mode — Program Selection', () => {
    it('renders program dropdown with loaded programs', async () => {
      renderCreate();
      await screen.findByText('New Project');

      await waitFor(() => {
        const programSelect = screen.getByLabelText(/program/i);
        const options = within(programSelect).getAllByRole('option');
        expect(options.map((o) => o.textContent)).toContain('Program Alpha');
      });
    });

    it('shows inline program creation form', async () => {
      const user = userEvent.setup();
      renderCreate();
      await screen.findByText('New Project');

      // "New" button next to program dropdown
      const generalSection = screen.getByText('General').closest('section')!;
      const newBtn = within(generalSection).getByRole('button', { name: /new/i });
      await user.click(newBtn);

      expect(screen.getByPlaceholderText('Program name')).toBeInTheDocument();
    });
  });

  describe('ProjectForm — original_budget', () => {
    it('renders the original-currency budget field and a read-only EUR field', async () => {
      server.use(
        http.get('/api/projects/budget-preview', () => HttpResponse.json({ budget_eur: 800 })),
      );
      renderCreate();
      expect(await screen.findByLabelText(/Budget in original currency/i)).toBeInTheDocument();
      expect(screen.getByText(/Budget \(EUR\)/i)).toBeInTheDocument();
      // Currency label no longer carries the "(invoices only...)" parenthetical
      expect(screen.queryByText(/invoices only/i)).not.toBeInTheDocument();
    });

    it('submits original_budget and omits budget', async () => {
      const user = userEvent.setup();
      let captured: Record<string, unknown> | null = null;
      server.use(
        http.get('/api/admin/integrations/status', () => HttpResponse.json(slackDisconnected)),
        http.get('/api/projects/budget-preview', () => HttpResponse.json({ budget_eur: 800 })),
        http.post('/api/projects', async ({ request }) => {
          captured = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ id: 'new-1' }, { status: 201 });
        }),
      );
      renderCreate();
      await screen.findByText('New Project');
      await user.click(screen.getByLabelText('Dependabot Alerts'));
      await user.type(screen.getByLabelText(/^Name/i), 'P1');
      await user.type(screen.getByLabelText(/^Code/i), 'P.1');
      await selectProgram(user);
      await user.type(screen.getByLabelText(/jira project key/i), 'P1');
      await user.type(screen.getByLabelText(/Budget in original currency/i), '1000');
      await user.type(screen.getByLabelText(/Start Date/i), '2026-01-01');
      await user.type(screen.getByLabelText(/End Date/i), '2026-12-31');
      await user.click(screen.getByRole('button', { name: /Create Project/i }));
      await waitFor(() => expect(captured).not.toBeNull());
      expect(captured!.original_budget).toBe(1000);
      expect(captured!).not.toHaveProperty('budget');
    });

    it('blocks submit when preview returns no rate', async () => {
      const user = userEvent.setup();
      let posted = false;
      server.use(
        http.get('/api/admin/integrations/status', () => HttpResponse.json(slackDisconnected)),
        http.get('/api/projects/budget-preview', () => HttpResponse.json({ budget_eur: null })),
        http.post('/api/projects', () => {
          posted = true;
          return HttpResponse.json({ id: 'x' }, { status: 201 });
        }),
      );
      renderCreate();
      await screen.findByText('New Project');
      await user.click(screen.getByLabelText('Dependabot Alerts'));
      await user.type(screen.getByLabelText(/^Name/i), 'P1');
      await user.type(screen.getByLabelText(/^Code/i), 'P.1');
      await selectProgram(user);
      await user.type(screen.getByLabelText(/jira project key/i), 'P1');
      await user.type(screen.getByLabelText(/Budget in original currency/i), '1000');
      await user.type(screen.getByLabelText(/Start Date/i), '2026-01-01');
      await user.type(screen.getByLabelText(/End Date/i), '2026-12-31');
      // Wait for the inline "no exchange rate" field hint to appear (query settled)
      await screen.findByText(/No exchange rate for this currency/i, { exact: false }, { timeout: 3000 });
      await user.click(screen.getByRole('button', { name: /Create Project/i }));
      // Both the inline field hint and the API error banner show a no-rate message
      const noRateMessages = await screen.findAllByText(/no exchange rate/i);
      expect(noRateMessages.length).toBeGreaterThanOrEqual(1);
      expect(posted).toBe(false);
    });
  });
});
