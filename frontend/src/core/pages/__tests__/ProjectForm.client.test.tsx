import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { server } from '@/test/setup';
import ProjectForm from '../ProjectForm';

const BASE = '/api';

const projectWithClient = {
  id: 'project-123',
  name: 'Test Project',
  code: 'TST.001',
  program_id: null,
  program_name: null,
  is_billable: true,
  has_scorecard: true,
  has_dependabot_alerts: true,
  has_budget_alerts: true,
  currency: 'euro',
  budget: 90000,
  original_budget: 100000,
  notes: null,
  summary: null,
  jira_project_key: null,
  github_repo: null,
  slack_channel_id: null,
  project_manager_id: null,
  project_manager_name: null,
  client_id: 'c-acme',
  client_name: 'Acme Foundation',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  status: 'live' as const,
  finished_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
};

const clientOptions = [
  { id: 'c-acme', name: 'Acme Foundation', code: 'ACM' },
  { id: 'c-beta', name: 'Beta Corp', code: null },
];

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
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

describe('ProjectForm — Client selector', () => {
  it('shows the linked client name in the trigger button', async () => {
    server.use(
      http.get(`${BASE}/projects/:id`, () => {
        return HttpResponse.json(projectWithClient);
      }),
      http.get(`${BASE}/clients/options`, () => {
        return HttpResponse.json(clientOptions);
      }),
    );

    renderEdit();
    await screen.findByText('Edit Project');

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /client/i })).toHaveTextContent('Acme Foundation');
    }, { timeout: 5000 });
  });

  it('shows "None" when no client is linked', async () => {
    server.use(
      http.get(`${BASE}/projects/:id`, () => {
        return HttpResponse.json({ ...projectWithClient, client_id: null, client_name: null });
      }),
      http.get(`${BASE}/clients/options`, () => {
        return HttpResponse.json(clientOptions);
      }),
    );

    renderEdit();
    await screen.findByText('Edit Project');

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /client/i })).toHaveTextContent('None');
    }, { timeout: 5000 });
  });
});
