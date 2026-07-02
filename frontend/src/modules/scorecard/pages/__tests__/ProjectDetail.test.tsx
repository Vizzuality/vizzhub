import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ProjectDetail from '../ProjectDetail';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import type { Project } from '@/core/types/project';
import type { ScoreResponse } from '../../types';

const mockProject: Project = {
  id: 'project-123',
  name: 'Test Project',
  jira_project_key: 'TEST',
  github_repo: 'org/test-repo',
  start_date: '2026-01-01',
  end_date: null,
  status: 'live',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
};

const mockScores: ScoreResponse = {
  indicators: {
    spi: 0.95,
    on_time_milestones: 0.8,
    cpi: 0.92,
    cost_variance_pct: 0.05,
    defect_density: 0.02,
    escaped_rate: 0.01,
    mttr_hours: 4,
    governance_compliance: 1.0,
    lead_time_days: 5,
    commitment_reliability: 0.85,
    pr_review_ratio: 0.95,
    prs_without_review: 2,
    high_vulns: 0,
    test_maturity: 0.8,
    arch_checklist: 0.75,
    story_review_ratio: 0.9,
    okr_impact: 0.7,
    pm_satisfaction: 0.85,
    client_satisfaction: 0.9,
    pr_size_median: 150,
    review_turnaround_hours: 8,
    deployment_frequency: 10,
    change_failure_rate: 0.05,
    post_contract_tasks: 2,
  },
  scores: {
    score: 82,
    dimensions: {
      p_time: 85,
      p_cost: 88,
      p_quality: 78,
      p_value: 75,
      p_satisfaction: 87,
      p_flow: 80,
      p_engineering: 82,
      p_risk: 90,
    },
    weights_applied: {},
    dora: null,
  },
};

const mockMetrics = {
  id: 'metrics-1',
  project_id: 'project-123',
  created_at: '2026-01-15T10:00:00Z',
  period_start: '2026-01-01',
  period_end: '2026-01-15',
  evm_data: {
    budget_total: 100000,
    cost_to_date: 45000,
    percent_completed: 50,
    percent_planned: 48,
  },
  milestones: [],
  sev1_incident: false,
};

const mockUseProjectScores = vi.fn(() => ({
  data: mockScores,
  isLoading: false,
  error: null,
}));

const mockUseProjectMetrics = vi.fn(() => ({
  data: mockMetrics,
  isLoading: false,
  error: null,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('@/core/hooks/useProjects', () => ({
  useDeleteProject: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateProjectStatus: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock('@/modules/scorecard/hooks/useScores', () => ({
  useProjectScores: () => mockUseProjectScores(),
}));

vi.mock('@/modules/scorecard/hooks/useMetrics', () => ({
  useProjectMetrics: () => mockUseProjectMetrics(),
  useUpdateGovernance: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdatePMSatisfaction: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateTestMaturity: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateArchitecture: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateStrategicImpact: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useUpdateClientSurvey: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock('@/modules/scorecard/hooks/usePeriodCapture', () => ({
  useCapturePeriod: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
    isSuccess: false,
    reset: vi.fn(),
  }),
}));

vi.mock('@/modules/scorecard/hooks/useConfig', () => ({
  useConfigParameters: () => ({
    data: {
      Targets: [],
      'Gates & Constants': [],
    },
    isLoading: false,
    error: null,
  }),
  useScoreThresholds: () => ({
    green: 80,
    yellow: 60,
  }),
}));

vi.mock('@/modules/scorecard/hooks/useSnapshots', () => ({
  useProjectSnapshots: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock('@/core/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'admin@test.com',
      first_name: null,
      last_name: null,
      picture: null,
      roles: ['user', 'admin'],
      permissions: ['*'],
      active: true,
    },
    permissions: ['*'],
    isImpersonating: false,
    isAuthenticated: true,
    isLoading: false,
  }),
}));

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderWithProviders(
  ui: React.ReactElement,
  project: Project = mockProject,
): ReturnType<typeof render> {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/project-123/scorecard']}>
        <ProjectProvider project={project}>
          {ui}
        </ProjectProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProjectScores.mockReturnValue({
      data: mockScores,
      isLoading: false,
      error: null,
    });
    mockUseProjectMetrics.mockReturnValue({
      data: mockMetrics,
      isLoading: false,
      error: null,
    });
  });

  describe('Facet body renders under ProjectProvider', () => {
    it('renders the scorecard body (SnapshotManager always present)', () => {
      renderWithProviders(<ProjectDetail />);

      expect(screen.getByText('Export')).toBeInTheDocument();
    });

    it('does not render a back-to-scorecard link', () => {
      renderWithProviders(<ProjectDetail />);

      expect(screen.queryByText(/back to scorecard/i)).toBeNull();
    });
  });

  describe('Scores Section', () => {
    it('shows no metrics message when scores error', () => {
      mockUseProjectScores.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('No scores'),
      });

      renderWithProviders(<ProjectDetail />);

      expect(screen.getByText(/no metrics available yet/i)).toBeInTheDocument();
    });

    it('shows loading spinner when scores loading', () => {
      mockUseProjectScores.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      renderWithProviders(<ProjectDetail />);

      expect(document.querySelectorAll('.animate-spin').length).toBeGreaterThan(0);
    });

    it('renders Scores heading when scores loaded', () => {
      renderWithProviders(<ProjectDetail />);

      expect(screen.getByText('Scores')).toBeInTheDocument();
    });
  });

  describe('Collect Metrics', () => {
    it('renders Collect Metrics button', () => {
      renderWithProviders(<ProjectDetail />);

      expect(screen.getByRole('button', { name: /collect metrics/i })).toBeInTheDocument();
    });
  });

});

