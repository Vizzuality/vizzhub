import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ISOReviews from '../ISOReviews';

const mockReview = {
  id: 'review-1',
  snapshot_id: 'snap-1',
  previous_snapshot_id: null,
  reviewer_id: null,
  status: 'draft' as const,
  scope: 'All users and groups',
  diff_summary: {
    total_changes: 3,
    new_user: 1,
    removed_user: 1,
    role_change: 1,
    new_external: 0,
    group_membership_change: 0,
  },
  notes: null,
  signed_by: null,
  signed_at: null,
  created_at: '2026-02-20T10:00:00Z',
  updated_at: '2026-02-20T10:00:00Z',
};

const mockUseIsoReviews = vi.fn();

vi.mock('../../hooks/useIso', () => ({
  useIsoReviews: (...args: unknown[]) => mockUseIsoReviews(...args),
}));

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderWithProviders(ui: React.ReactElement): ReturnType<typeof render> {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ISOReviews', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsoReviews.mockReturnValue({
      data: {
        items: [mockReview],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1,
      },
      isLoading: false,
    });
  });

  it('renders loading spinner when isLoading is true', () => {
    mockUseIsoReviews.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    renderWithProviders(<ISOReviews />);

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows empty state when no reviews', () => {
    mockUseIsoReviews.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 },
      isLoading: false,
    });

    renderWithProviders(<ISOReviews />);

    expect(screen.getByText(/no reviews found/i)).toBeInTheDocument();
  });

  it('shows review table with correct columns', () => {
    renderWithProviders(<ISOReviews />);

    expect(screen.getByText('Created')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Scope')).toBeInTheDocument();
    expect(screen.getByText('Changes')).toBeInTheDocument();
    expect(screen.getByText('Signed')).toBeInTheDocument();
  });

  it('shows review data in the table', () => {
    renderWithProviders(<ISOReviews />);

    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('All users and groups')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('\u2014')).toBeInTheDocument();
  });

  it('renders status filter dropdown', () => {
    renderWithProviders(<ISOReviews />);

    expect(screen.getByText('All statuses')).toBeInTheDocument();
  });

  it('hides pagination controls when total_pages <= 1', () => {
    renderWithProviders(<ISOReviews />);

    expect(screen.queryByText(/page 1 of/i)).not.toBeInTheDocument();
  });
});
