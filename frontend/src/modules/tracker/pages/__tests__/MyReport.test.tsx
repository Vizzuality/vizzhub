import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import { AuthContext } from '@/core/contexts/AuthContext';
import type { AuthContextType } from '@/core/types/auth';
import MyReport from '../MyReport';

const AUTH_EMAIL = 'admin@test.com';

const mockAuth: AuthContextType = {
  user: { id: 'user-1', email: AUTH_EMAIL, role: 'admin' },
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

const reportWithMatchingEmail = {
  id: 'report-1',
  user_id: 'user-1',
  reporting_period_id: 'period-1',
  estimated: false,
  user_name: 'Admin User',
  user_email: AUTH_EMAIL,
  created_at: '2026-03-01T00:00:00Z',
  updated_at: '2026-03-01T00:00:00Z',
};

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderMyReport(path = '/tracker/my-report'): ReturnType<typeof render> {
  return render(
    <AuthContext.Provider value={mockAuth}>
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/tracker/my-report" element={<MyReport />} />
            <Route path="/tracker/my-report/:periodId" element={<MyReport />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

describe('MyReport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  it('shows period title and status badge for active period', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([reportWithMatchingEmail]);
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(screen.getByText(/March 2026/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText('active').length).toBeGreaterThanOrEqual(1);
  });

  it('displays report editor when user has a report', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([reportWithMatchingEmail]);
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(screen.getByText('My Time Report')).toBeInTheDocument();
    });
  });

  it('auto-creates report when active period has no report for user', async () => {
    let createCalled = false;

    server.use(
      http.get('/api/tracker/reports', () => {
        if (createCalled) {
          return HttpResponse.json([reportWithMatchingEmail]);
        }
        return HttpResponse.json([]);
      }),
      http.post('/api/tracker/reports', async () => {
        createCalled = true;
        return HttpResponse.json(reportWithMatchingEmail, { status: 201 });
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(createCalled).toBe(true);
    });
  });

  it('shows report parts with project name and days', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([reportWithMatchingEmail]);
      }),
      http.get('/api/tracker/reports/:id', () => {
        return HttpResponse.json({
          ...reportWithMatchingEmail,
          parts: [
            {
              id: 'part-1',
              report_id: 'report-1',
              project_id: 'project-123',
              project_name: 'Test Project',
              functional_area_id: null,
              percentage: 0.2,
              days: 2.96,
              cost: 2274.02,
              created_at: '2026-03-15T00:00:00Z',
              updated_at: '2026-03-15T00:00:00Z',
            },
          ],
        });
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
    expect(screen.getAllByText('2.96').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByDisplayValue('20.0')).toBeInTheDocument();
  });

  it('shows add project dropdown when report has no parts', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([reportWithMatchingEmail]);
      }),
      http.get('/api/tracker/reports/:id', () => {
        return HttpResponse.json({
          ...reportWithMatchingEmail,
          parts: [],
        });
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(screen.getByText('My Time Report')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('Add project...')).toBeInTheDocument();
    });
    expect(screen.getByText('0 projects')).toBeInTheDocument();
  });

  it('shows no active period message when none exists', async () => {
    server.use(
      http.get('/api/tracker/reporting-periods', () => {
        return HttpResponse.json([
          {
            id: 'period-old',
            date: '2026-01-01',
            base_rate: 175,
            status: 'finished',
            report_count: 2,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ]);
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(
        screen.getByText(/No active reporting period/),
      ).toBeInTheDocument();
    });
  });

  it('shows How to report and Report history buttons', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([reportWithMatchingEmail]);
      }),
    );

    renderMyReport();

    await waitFor(() => {
      expect(screen.getByText('How to report')).toBeInTheDocument();
    });
    expect(screen.getByText('Report history')).toBeInTheDocument();
  });

  it('shows no report message for non-active period without report', async () => {
    server.use(
      http.get('/api/tracker/reports', () => {
        return HttpResponse.json([]);
      }),
    );

    renderMyReport('/tracker/my-report/period-2');

    await waitFor(() => {
      expect(
        screen.getByText('No report for this period.'),
      ).toBeInTheDocument();
    });
  });
});
