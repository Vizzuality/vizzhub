import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import PeriodDetail from '../PeriodDetail';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderDetail(periodId: string = 'period-1'): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/admin/tracker/periods/${periodId}`]}>
        <Routes>
          <Route path="/admin/tracker/periods/:periodId" element={<PeriodDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PeriodDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  it('renders period header with month and status', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/March 2026/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText('active').length).toBeGreaterThanOrEqual(1);
  });

  it('renders reports as collapsed cards with user name', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
  });

  it('shows report parts after expanding a report', async () => {
    const user = userEvent.setup();
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
    await user.click(screen.getByText('Test User'));
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  it('handles period not found', async () => {
    server.use(
      http.get('/api/tracker/reporting-periods/:id', () => {
        return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
      }),
    );

    renderDetail('nonexistent');

    await waitFor(() => {
      expect(screen.getByText(/error loading period/i)).toBeInTheDocument();
    });
  });

  it('shows inline project selector after expanding a report', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('/api/projects', ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get('lightweight') === 'true') {
          return HttpResponse.json([
            { id: 'project-123', name: 'Test Project' },
            { id: 'project-456', name: 'Other Project' },
          ]);
        }
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 45 });
      }),
    );

    renderDetail();

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
    await user.click(screen.getByText('Test User'));
    await waitFor(() => {
      expect(screen.getByText('Add project...')).toBeInTheDocument();
    });
  });
});
