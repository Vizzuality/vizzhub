import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CopperCard from '../CopperCard';
import { integrationsApi } from '@/core/services/integrations';
import type { ProviderStatus } from '@/core/services/integrations';

vi.mock('@/core/services/integrations', () => ({
  integrationsApi: {
    saveCopperCredentials: vi.fn(),
    deleteCopper: vi.fn(),
  },
}));

const DISCONNECTED: ProviderStatus = {
  connected: false,
  expires_at: null,
  token_type: null,
  site_url: null,
  created_at: null,
};

function renderCard(status: ProviderStatus, userEmail: string | null = null): void {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CopperCard status={status} userEmail={userEmail} />
    </QueryClientProvider>
  );
}

describe('CopperCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends the API key and the key owner email', async () => {
    vi.mocked(integrationsApi.saveCopperCredentials).mockResolvedValue({
      ...DISCONNECTED,
      connected: true,
    });
    renderCard(DISCONNECTED);

    await userEvent.type(screen.getByLabelText(/api key/i), 'key-123');
    await userEvent.type(screen.getByLabelText(/email/i), 'owner@example.com');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() =>
      expect(integrationsApi.saveCopperCredentials).toHaveBeenCalledWith(
        'key-123',
        'owner@example.com'
      )
    );
  });

  it('shows why Copper rejected the credentials', async () => {
    vi.mocked(integrationsApi.saveCopperCredentials).mockRejectedValue({
      response: { data: { detail: 'Copper rejected this API key and email.' } },
    });
    renderCard(DISCONNECTED);

    await userEvent.type(screen.getByLabelText(/api key/i), 'bad');
    await userEvent.type(screen.getByLabelText(/email/i), 'typo@example.com');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(await screen.findByText(/copper rejected this api key/i)).toBeInTheDocument();
  });

  it('shows the connected account email and offers to disconnect', () => {
    renderCard({ ...DISCONNECTED, connected: true }, 'owner@example.com');

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('owner@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /disconnect/i })).toBeInTheDocument();
  });
});
