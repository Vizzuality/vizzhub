import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ISOSnapshotDetail from '../ISOSnapshotDetail';

const mockSnapshot = {
  id: 'snap-1',
  provider: 'google_workspace',
  captured_at: '2026-02-20T10:00:00Z',
  captured_by: null,
  data_version: '1',
  source_metadata: { domain: 'test.com' },
  data: {
    users: [
      {
        id: 'u1',
        name: 'Alice',
        email: 'alice@test.com',
        suspended: false,
        org_unit_path: '/',
      },
    ],
    groups: [
      { id: 'g1', name: 'Engineering', email: 'eng@test.com' },
    ],
    group_members: {
      'eng@test.com': [
        { email: 'alice@test.com', role: 'MEMBER', type: 'USER' },
      ],
    },
    role_assignments: [
      {
        role_id: 'r1',
        user_id: 'u1',
        role_name: 'Super Admin',
        user_email: 'alice@test.com',
      },
    ],
  },
  summary: {
    total_users: 1,
    total_admins: 1,
    total_groups: 1,
    external_members: 0,
  },
  created_at: '2026-02-20T10:00:00Z',
};

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

const mockUseIsoSnapshot = vi.fn();
const mockUseSnapshotReview = vi.fn();
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
    useParams: () => ({ id: 'snap-1' }),
  };
});

vi.mock('../../hooks/useIso', () => ({
  useIsoSnapshot: (...args: unknown[]) => mockUseIsoSnapshot(...args),
  useSnapshotReview: (...args: unknown[]) => mockUseSnapshotReview(...args),
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

describe('ISOSnapshotDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsoSnapshot.mockReturnValue({
      data: mockSnapshot,
      isLoading: false,
      error: null,
    });
    mockUseSnapshotReview.mockReturnValue({
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

  // --- Snapshot section ---

  it('renders loading spinner when snapshot is loading', () => {
    mockUseIsoSnapshot.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error state when snapshot fails to load', () => {
    mockUseIsoSnapshot.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed'),
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Failed to load snapshot.')).toBeInTheDocument();
    expect(screen.getByText('Back to Snapshots')).toBeInTheDocument();
  });

  it('shows snapshot header with provider badge', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Snapshot Detail')).toBeInTheDocument();
    expect(screen.getByText('google_workspace')).toBeInTheDocument();
  });

  it('shows summary stat cards', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Total Users')).toBeInTheDocument();
    expect(screen.getByText('Total Admins')).toBeInTheDocument();
    expect(screen.getByText('Total Groups')).toBeInTheDocument();
    expect(screen.getByText('External Members')).toBeInTheDocument();
  });

  it('shows data tabs (Users, Groups, Group Members, Admins)', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Groups')).toBeInTheDocument();
    expect(screen.getByText('Group Members')).toBeInTheDocument();
    expect(screen.getByText('Admins')).toBeInTheDocument();
  });

  it('renders users table by default', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('alice@test.com')).toBeInTheDocument();
  });

  // --- Review section ---

  it('shows review status badge in header when review exists', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Draft')).toBeInTheDocument();
  });

  it('shows review details card with scope and notes', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Review Details')).toBeInTheDocument();
    expect(screen.getByText('All users and groups')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test notes')).toBeInTheDocument();
  });

  it('shows diff summary stat cards', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Diff Summary')).toBeInTheDocument();
    expect(screen.getByText('New Users')).toBeInTheDocument();
    expect(screen.getByText('Removed Users')).toBeInTheDocument();
    expect(screen.getByText('Role Changes')).toBeInTheDocument();
    expect(screen.getByText('New External')).toBeInTheDocument();
    expect(screen.getByText('Group Changes')).toBeInTheDocument();
  });

  it('renders actions table with subject labels', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
    expect(screen.getByText(/Jane Smith/)).toBeInTheDocument();
  });

  it('shows color-coded change type badges', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    const newUserBadge = screen.getByText('New User');
    expect(newUserBadge.className).toContain('green');

    const removedUserBadge = screen.getByText('Removed User');
    expect(removedUserBadge.className).toContain('red');
  });

  it('shows unresolved count when actions are pending', () => {
    renderWithProviders(<ISOSnapshotDetail />);

    expect(
      screen.getByText(/1 action still unresolved/i),
    ).toBeInTheDocument();
  });

  it('shows "Ready to sign" when all actions resolved', () => {
    const allResolved = {
      ...mockReviewDetail,
      actions: mockReviewDetail.actions.map((a) => ({
        ...a,
        action_taken: 'accepted' as const,
        justification: 'OK',
      })),
    };
    mockUseSnapshotReview.mockReturnValue({
      data: allResolved,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(
      screen.getByText(/all actions resolved\. ready to sign\./i),
    ).toBeInTheDocument();
  });

  it('disables sign button when there are unresolved actions', () => {
    renderWithProviders(<ISOSnapshotDetail />);

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
    mockUseSnapshotReview.mockReturnValue({
      data: signedReview,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByRole('button', { name: /unsign review/i })).toBeInTheDocument();
  });

  it('shows signed date in header when review is signed', () => {
    const signedReview = {
      ...mockReviewDetail,
      status: 'signed' as const,
      signed_at: '2026-02-21T10:00:00Z',
    };
    mockUseSnapshotReview.mockReturnValue({
      data: signedReview,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText(/Signed Feb/)).toBeInTheDocument();
  });

  it('shows exception date picker when action is exception', () => {
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
    mockUseSnapshotReview.mockReturnValue({
      data: exceptionReview,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    const dateInput = document.querySelector('input[type="date"]');
    expect(dateInput).toBeTruthy();
  });

  // --- No review scenario ---

  it('does not render review section when no review exists', () => {
    mockUseSnapshotReview.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Snapshot Detail')).toBeInTheDocument();
    expect(screen.queryByText('Review Details')).not.toBeInTheDocument();
    expect(screen.queryByTestId('review-panel')).not.toBeInTheDocument();
  });

  it('still shows snapshot data when no review exists', () => {
    mockUseSnapshotReview.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOSnapshotDetail />);

    expect(screen.getByText('Total Users')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });
});
