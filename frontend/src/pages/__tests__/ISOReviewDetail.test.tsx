import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ISOReviewDetail from '../ISOReviewDetail';

const mockReviewDetail = {
  id: 'review-1',
  snapshot_id: 'snap-1',
  previous_snapshot_id: 'snap-0',
  reviewer_id: null,
  status: 'draft' as const,
  scope: 'All users and groups',
  diff_summary: {
    total_changes: 2,
    new_user: 1,
    removed_user: 1,
    role_change: 0,
    new_external: 0,
    group_membership_change: 0,
  },
  notes: 'Test notes',
  signed_by: null,
  signed_at: null,
  created_at: '2026-02-20T10:00:00Z',
  updated_at: '2026-02-20T10:00:00Z',
  actions: [
    {
      id: 'action-1',
      review_id: 'review-1',
      subject_type: 'user' as const,
      subject_id: 'u1',
      subject_label: 'John Doe',
      change_type: 'new_user',
      previous_value: null,
      current_value: { email: 'john@example.com' },
      action_taken: 'accepted' as const,
      justification: 'New hire',
      approved_by: null,
      exception_until: null,
      created_at: '2026-02-20T10:00:00Z',
      updated_at: '2026-02-20T10:00:00Z',
    },
    {
      id: 'action-2',
      review_id: 'review-1',
      subject_type: 'user' as const,
      subject_id: 'u2',
      subject_label: 'Jane Smith',
      change_type: 'removed_user',
      previous_value: { email: 'jane@example.com' },
      current_value: null,
      action_taken: null,
      justification: null,
      approved_by: null,
      exception_until: null,
      created_at: '2026-02-20T10:00:00Z',
      updated_at: '2026-02-20T10:00:00Z',
    },
  ],
};

const mockUseIsoReview = vi.fn();
const mockUpdateMutate = vi.fn();
const mockUseUpdateReview = vi.fn();
const mockUseUpdateReviewAction = vi.fn();
const mockSignMutate = vi.fn();
const mockUseSignReview = vi.fn();
const mockUnsignMutate = vi.fn();
const mockUseUnsignReview = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'review-1' }),
  };
});

vi.mock('../../hooks/useIso', () => ({
  useIsoReview: (...args: unknown[]) => mockUseIsoReview(...args),
  useUpdateReview: (...args: unknown[]) => mockUseUpdateReview(...args),
  useUpdateReviewAction: (...args: unknown[]) => mockUseUpdateReviewAction(...args),
  useSignReview: (...args: unknown[]) => mockUseSignReview(...args),
  useUnsignReview: (...args: unknown[]) => mockUseUnsignReview(...args),
}));

vi.mock('../../hooks/useUsers', () => ({
  useUsers: () => ({ data: [] }),
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

describe('ISOReviewDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsoReview.mockReturnValue({
      data: mockReviewDetail,
      isLoading: false,
      error: null,
    });
    mockUseUpdateReview.mockReturnValue({
      mutate: mockUpdateMutate,
      isPending: false,
    });
    mockUseUpdateReviewAction.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
    mockUseSignReview.mockReturnValue({
      mutate: mockSignMutate,
      isPending: false,
    });
    mockUseUnsignReview.mockReturnValue({
      mutate: mockUnsignMutate,
      isPending: false,
    });
  });

  it('renders loading spinner when isLoading is true', () => {
    mockUseIsoReview.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProviders(<ISOReviewDetail />);

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error state when review fails to load', () => {
    mockUseIsoReview.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed'),
    });

    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Failed to load review.')).toBeInTheDocument();
  });

  it('shows review header with status badge and dates', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Access Review')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });

  it('shows review details card with scope and notes textarea', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Review Details')).toBeInTheDocument();
    expect(screen.getByText('All users and groups')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test notes')).toBeInTheDocument();
  });

  it('shows diff summary stat cards when diff_summary exists', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Diff Summary')).toBeInTheDocument();
    expect(screen.getByText('New Users')).toBeInTheDocument();
    expect(screen.getByText('Removed Users')).toBeInTheDocument();
    expect(screen.getByText('Role Changes')).toBeInTheDocument();
    expect(screen.getByText('New External')).toBeInTheDocument();
    expect(screen.getByText('Group Changes')).toBeInTheDocument();
  });

  it('renders actions table with subject labels', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
    expect(screen.getByText(/Jane Smith/)).toBeInTheDocument();
  });

  it('shows color-coded change_type badges', () => {
    renderWithProviders(<ISOReviewDetail />);

    const newUserBadge = screen.getByText('New User');
    expect(newUserBadge.className).toContain('green');

    const removedUserBadge = screen.getByText('Removed User');
    expect(removedUserBadge.className).toContain('red');
  });

  it('shows unresolved count when some actions are pending', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(
      screen.getByText(/1 action still unresolved/i),
    ).toBeInTheDocument();
  });

  it('shows "All actions resolved. Ready to sign." when all actions have action_taken', () => {
    const allResolved = {
      ...mockReviewDetail,
      actions: mockReviewDetail.actions.map((a) => ({
        ...a,
        action_taken: 'accepted' as const,
        justification: 'OK',
      })),
    };
    mockUseIsoReview.mockReturnValue({
      data: allResolved,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOReviewDetail />);

    expect(
      screen.getByText(/all actions resolved\. ready to sign\./i),
    ).toBeInTheDocument();
  });

  it('disables sign button when there are unresolved actions', () => {
    renderWithProviders(<ISOReviewDetail />);

    const signButton = screen.getByRole('button', { name: /sign review/i });
    expect(signButton).toBeDisabled();
  });

  it('shows unsign button when review is signed', () => {
    const signedReview = {
      ...mockReviewDetail,
      status: 'signed' as const,
      signed_by: 'user-1',
      signed_at: '2026-02-21T10:00:00Z',
      actions: mockReviewDetail.actions.map((a) => ({
        ...a,
        action_taken: 'accepted' as const,
      })),
    };
    mockUseIsoReview.mockReturnValue({
      data: signedReview,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByRole('button', { name: /unsign review/i })).toBeInTheDocument();
  });

  it('shows justification field as textarea', () => {
    renderWithProviders(<ISOReviewDetail />);

    const textareas = document.querySelectorAll('textarea[placeholder="Justification..."]');
    expect(textareas.length).toBeGreaterThan(0);
  });

  it('shows exception date picker when action_taken is exception', () => {
    const exceptionReview = {
      ...mockReviewDetail,
      actions: [
        {
          ...mockReviewDetail.actions[0],
          action_taken: 'exception' as const,
          exception_until: '2026-06-01',
        },
      ],
    };
    mockUseIsoReview.mockReturnValue({
      data: exceptionReview,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOReviewDetail />);

    const dateInput = document.querySelector('input[type="date"]');
    expect(dateInput).toBeTruthy();
  });

  it('shows Back to Reviews link', () => {
    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Back to Reviews')).toBeInTheDocument();
  });

  it('shows Back to Reviews link on error state', () => {
    mockUseIsoReview.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Not found'),
    });

    renderWithProviders(<ISOReviewDetail />);

    expect(screen.getByText('Back to Reviews')).toBeInTheDocument();
  });
});
