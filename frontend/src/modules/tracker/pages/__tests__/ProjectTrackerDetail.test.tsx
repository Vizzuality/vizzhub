import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import type { Project } from '@/core/types/project';
import ProjectTrackerDetail from '../ProjectTrackerDetail';

const mockProject: Project = {
  id: 'project-1',
  name: 'Test Project',
  code: 'TP-1',
  program_id: null,
  program_name: null,
  is_billable: true,
  has_scorecard: false,
  has_dependabot_alerts: false,
  has_budget_alerts: false,
  currency: 'euro',
  budget: 50000,
  notes: null,
  summary: null,
  jira_project_key: null,
  github_repo: null,
  slack_channel_id: null,
  project_manager_id: null,
  project_manager_name: null,
  client_id: null,
  client_name: null,
  start_date: null,
  end_date: null,
  status: 'live',
  finished_at: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

vi.mock('@/core/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'user@test.com',
      first_name: null,
      last_name: null,
      picture: null,
      roles: ['user'],
      permissions: ['scorecard:view', 'scorecard:edit_metrics', 'tracker:view', 'tracker:manage_own_reports', 'projects:view'],
      active: true,
    },
    permissions: ['scorecard:view', 'scorecard:edit_metrics', 'tracker:view', 'tracker:manage_own_reports', 'projects:view'],
    isAuthenticated: true,
    isLoading: false,
    isImpersonating: false,
  }),
}));

function renderDetail(project: Project = mockProject): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/projects/${project.id}/tracker`]}>
        <ProjectProvider project={project}>
          <ProjectTrackerDetail />
        </ProjectProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProjectTrackerDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  it('renders budget card with summary data', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/50\.000,00/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/3\.911,03/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/of budget/)).toBeInTheDocument();
  });

  it('renders reports table with parts', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getAllByText('Test User').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getAllByText('Backend Developer').length).toBeGreaterThanOrEqual(1);
  });

  it('renders time by area table', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Time per Functional Area')).toBeInTheDocument();
    });
    expect(screen.getAllByText('4.4').length).toBeGreaterThanOrEqual(1);
  });

  it('shows days by people expanded by default', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Days by People')).toBeInTheDocument();
    });
  });

  it('shows empty state for project with no data', async () => {
    server.use(
      http.get('/api/tracker/projects/:projectId/cost-summary', () => {
        return HttpResponse.json({
          project_id: 'project-empty',
          budget: null,
          contract_rate: 175,
          staff_cost: 0,
          non_staff_cost: 0,
          total_cost: 0,
          burn_percentage: null,
          periods: [],
        });
      }),
      http.get('/api/tracker/projects/:projectId/report-parts', () => {
        return HttpResponse.json([]);
      }),
    );

    renderDetail({ ...mockProject, id: 'project-empty' });

    await waitFor(() => {
      expect(screen.getByText('No report data')).toBeInTheDocument();
    });
  });

  it('filters by period when selecting from dropdown', async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.getByText(/50\.000/)).toBeInTheDocument();
    });

    const select = screen.getByLabelText('Period');
    await user.selectOptions(select, 'period-1');
    expect(select).toHaveValue('period-1');
  });

  it('does not render the inline Back button', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/50\.000/)).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /back/i })).toBeNull();
  });

  it('renders the period select (URL-driven filter)', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByLabelText('Period')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Period')).toHaveValue('');
  });
});
