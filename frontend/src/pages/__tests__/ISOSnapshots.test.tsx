import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ISOSnapshots from '../ISOSnapshots';

const mockSnapshot = {
  id: 'snap-1',
  provider: 'google_workspace',
  captured_at: '2026-02-20T10:00:00Z',
  captured_by: null,
  data_version: '1',
  summary: { total_users: 25, total_admins: 3, total_groups: 5, external_members: 2 },
  created_at: '2026-02-20T10:00:00Z',
};

const mockUseIsoSnapshots = vi.fn();
const mockCaptureMutate = vi.fn();
const mockUseCaptureSnapshot = vi.fn();
const mockIsSnapshotStale = vi.fn();

vi.mock('../../hooks/useIso', () => ({
  useIsoSnapshots: (...args: unknown[]) => mockUseIsoSnapshots(...args),
  useCaptureSnapshot: () => mockUseCaptureSnapshot(),
}));

vi.mock('../../hooks/isoStaleCheck', () => ({
  isSnapshotStale: (...args: unknown[]) => mockIsSnapshotStale(...args),
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

describe('ISOSnapshots', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCaptureSnapshot.mockReturnValue({
      mutate: mockCaptureMutate,
      isPending: false,
      isError: false,
    });
    mockIsSnapshotStale.mockReturnValue(false);
    mockUseIsoSnapshots.mockReturnValue({
      data: {
        items: [mockSnapshot],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1,
      },
      isLoading: false,
    });
  });

  it('renders loading spinner when isLoading is true', () => {
    mockUseIsoSnapshots.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    renderWithProviders(<ISOSnapshots />);

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows empty state when data has 0 items', () => {
    mockUseIsoSnapshots.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 },
      isLoading: false,
    });

    renderWithProviders(<ISOSnapshots />);

    expect(screen.getByText(/no snapshots have been captured yet/i)).toBeInTheDocument();
  });

  it('shows snapshot table with correct data', () => {
    renderWithProviders(<ISOSnapshots />);

    expect(screen.getByText('google_workspace')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows stale warning banner when isSnapshotStale returns true', () => {
    mockIsSnapshotStale.mockReturnValue(true);

    renderWithProviders(<ISOSnapshots />);

    expect(
      screen.getByText(/last access snapshot is over 35 days old/i),
    ).toBeInTheDocument();
  });

  it('does not show stale warning when snapshot is recent', () => {
    mockIsSnapshotStale.mockReturnValue(false);

    renderWithProviders(<ISOSnapshots />);

    expect(
      screen.queryByText(/last access snapshot is over 35 days old/i),
    ).not.toBeInTheDocument();
  });

  it('shows different stale message when no snapshots exist', () => {
    mockIsSnapshotStale.mockReturnValue(true);
    mockUseIsoSnapshots.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20, pages: 0 },
      isLoading: false,
    });

    renderWithProviders(<ISOSnapshots />);

    expect(
      screen.getByText(/no access snapshots have been captured yet/i),
    ).toBeInTheDocument();
  });

  it('calls capture.mutate() when capture button is clicked', () => {
    renderWithProviders(<ISOSnapshots />);

    const captureButton = screen.getByRole('button', { name: /capture snapshot/i });
    fireEvent.click(captureButton);

    expect(mockCaptureMutate).toHaveBeenCalledOnce();
  });

  it('shows "Capturing..." text when capture is pending', () => {
    mockUseCaptureSnapshot.mockReturnValue({
      mutate: mockCaptureMutate,
      isPending: true,
      isError: false,
    });

    renderWithProviders(<ISOSnapshots />);

    expect(screen.getByText('Capturing...')).toBeInTheDocument();
  });

  it('shows error banner when capture fails', () => {
    mockUseCaptureSnapshot.mockReturnValue({
      mutate: mockCaptureMutate,
      isPending: false,
      isError: true,
    });

    renderWithProviders(<ISOSnapshots />);

    expect(
      screen.getByText(/failed to capture snapshot/i),
    ).toBeInTheDocument();
  });

  it('hides pagination controls when only 1 page', () => {
    renderWithProviders(<ISOSnapshots />);

    expect(screen.queryByText(/page 1 of/i)).not.toBeInTheDocument();
  });
});
