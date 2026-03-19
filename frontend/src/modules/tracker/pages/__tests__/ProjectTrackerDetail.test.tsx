import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import ProjectTrackerDetail from '../ProjectTrackerDetail';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderDetail(projectId: string = 'project-1'): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/tracker/projects/${projectId}`]}>
        <Routes>
          <Route path="/tracker/projects/:projectId" element={<ProjectTrackerDetail />} />
        </Routes>
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
    expect(screen.getAllByText('4.44').length).toBeGreaterThanOrEqual(1);
  });

  it('shows days by people after expanding details', async () => {
    const user = userEvent.setup();
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/Show more/)).toBeInTheDocument();
    });
    await user.click(screen.getByText(/Show more/));
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

    renderDetail('project-empty');

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
});
