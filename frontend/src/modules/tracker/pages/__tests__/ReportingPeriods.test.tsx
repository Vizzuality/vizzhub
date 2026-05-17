import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import ReportingPeriods from '../ReportingPeriods';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderPage(): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={['/admin/tracker/periods']}>
        <ReportingPeriods />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ReportingPeriods', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  it('renders periods list', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/March 2026/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/February 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/April 2026/i)).toBeInTheDocument();
  });

  it('shows status badges', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('active')).toBeInTheDocument();
    });
    expect(screen.getByText('finished')).toBeInTheDocument();
    expect(screen.getByText('unstarted')).toBeInTheDocument();
  });

  it('shows action buttons per status', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Finish')).toBeInTheDocument();
    });
    expect(screen.getByText('Reactivate')).toBeInTheDocument();
    expect(screen.getByText('Activate')).toBeInTheDocument();
    const trashButtons = screen.getAllByRole('button').filter(
      (btn) => btn.closest('td') && btn.querySelector('svg'),
    );
    expect(trashButtons.length).toBe(1);
  });

  it('creates a new period', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('New Period')).toBeInTheDocument();
    });

    await user.click(screen.getByText('New Period'));
    await waitFor(() => {
      expect(screen.getByText('Create Reporting Period')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Create'));

    await waitFor(() => {
      expect(screen.queryByText('Create Reporting Period')).not.toBeInTheDocument();
    });
  });

  it('activates an unstarted period', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Activate')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Activate'));

    await waitFor(() => {
      expect(screen.getByText('Activate')).toBeInTheDocument();
    });
  });

  it('navigates to period detail on row click', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/March 2026/i)).toBeInTheDocument();
    });

    const row = screen.getByText(/March 2026/i).closest('tr');
    if (row) await user.click(row);

    expect(mockNavigate).toHaveBeenCalledWith('/admin/tracker/periods/period-1');
  });

  it('handles API error', async () => {
    server.use(
      http.get('/api/tracker/reporting-periods', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/error loading periods/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no periods', async () => {
    server.use(
      http.get('/api/tracker/reporting-periods', () => {
        return HttpResponse.json([]);
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no reporting periods yet/i)).toBeInTheDocument();
    });
  });
});
