import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import GoogleWorkspaceCard from '@/modules/scorecard/components/Settings/GoogleWorkspaceCard';

const mockUseIsoConfig = vi.fn();
const mockDisconnectMutate = vi.fn();

vi.mock('@/modules/iso/hooks/useIso', () => ({
  useIsoConfig: () => mockUseIsoConfig(),
  useDisconnectGoogleWorkspace: () => ({
    mutate: mockDisconnectMutate,
    isPending: false,
  }),
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

describe('GoogleWorkspaceCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIsoConfig.mockReturnValue({
      data: { connected: false, domain: null },
      isLoading: false,
      error: null,
    });
  });

  it('shows "Not connected" badge when not connected', () => {
    renderWithProviders(<GoogleWorkspaceCard />);

    expect(screen.getByText('Not connected')).toBeInTheDocument();
  });

  it('shows "Connected" badge and domain when connected', () => {
    mockUseIsoConfig.mockReturnValue({
      data: { connected: true, domain: 'example.com' },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<GoogleWorkspaceCard />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('example.com')).toBeInTheDocument();
  });

  it('shows "Connect Google Workspace" button when not connected', () => {
    renderWithProviders(<GoogleWorkspaceCard />);

    expect(
      screen.getByRole('button', { name: /connect google workspace/i }),
    ).toBeInTheDocument();
  });

  it('shows "Disconnect" button when connected', () => {
    mockUseIsoConfig.mockReturnValue({
      data: { connected: true, domain: 'example.com' },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<GoogleWorkspaceCard />);

    expect(
      screen.getByRole('button', { name: /disconnect/i }),
    ).toBeInTheDocument();
  });

  it('disconnect button opens confirmation dialog', () => {
    mockUseIsoConfig.mockReturnValue({
      data: { connected: true, domain: 'example.com' },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<GoogleWorkspaceCard />);

    fireEvent.click(screen.getByRole('button', { name: /disconnect/i }));

    expect(screen.getByText('Disconnect Google Workspace?')).toBeInTheDocument();
  });
});
