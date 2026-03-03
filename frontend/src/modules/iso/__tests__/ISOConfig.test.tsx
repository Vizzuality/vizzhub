import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ISOConfig from '../pages/ISOConfig';

const mockUseIsoConfig = vi.fn();
const mockDisconnectMutate = vi.fn();
const mockUseDisconnectGoogleWorkspace = vi.fn();

vi.mock('../hooks/useIso', () => ({
  useIsoConfig: (...args: unknown[]) => mockUseIsoConfig(...args),
  useDisconnectGoogleWorkspace: () => mockUseDisconnectGoogleWorkspace(),
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

describe('ISOConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDisconnectGoogleWorkspace.mockReturnValue({
      mutate: mockDisconnectMutate,
      isPending: false,
    });
    mockUseIsoConfig.mockReturnValue({
      data: { connected: false, domain: null },
      isLoading: false,
      error: null,
    });
  });

  it('renders loading spinner when isLoading is true', () => {
    mockUseIsoConfig.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProviders(<ISOConfig />);

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error banner when config fails to load', () => {
    mockUseIsoConfig.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Server error'),
    });

    renderWithProviders(<ISOConfig />);

    expect(
      screen.getByText('Failed to load configuration status.'),
    ).toBeInTheDocument();
  });

  it('shows "Not connected" badge when not connected', () => {
    renderWithProviders(<ISOConfig />);

    expect(screen.getByText('Not connected')).toBeInTheDocument();
  });

  it('shows "Connected" badge and domain when connected', () => {
    mockUseIsoConfig.mockReturnValue({
      data: { connected: true, domain: 'example.com' },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ISOConfig />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('example.com')).toBeInTheDocument();
  });

  it('shows "Connect Google Workspace" button when not connected', () => {
    renderWithProviders(<ISOConfig />);

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

    renderWithProviders(<ISOConfig />);

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

    renderWithProviders(<ISOConfig />);

    const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
    fireEvent.click(disconnectButton);

    expect(
      screen.getByText('Disconnect Google Workspace?'),
    ).toBeInTheDocument();
  });
});
