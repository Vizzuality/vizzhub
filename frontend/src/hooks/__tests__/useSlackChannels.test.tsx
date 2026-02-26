import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSlackChannels } from '../useSlackChannels';
import { integrationsApi } from '../../services/api/integrations';
import type { SlackChannel } from '../../types';
import type { AllIntegrationsStatus } from '../../services/api/integrations';

vi.mock('../../services/api/integrations', () => ({
  integrationsApi: {
    getStatus: vi.fn(),
    getSlackChannels: vi.fn(),
  },
}));

const mockSlackChannels: SlackChannel[] = [
  { id: 'C123', name: 'general', is_private: false },
  { id: 'C456', name: 'engineering', is_private: false },
];

const makeStatus = (slackConnected: boolean): AllIntegrationsStatus => ({
  jira: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  google_workspace: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  github: { connected: false, expires_at: null, token_type: null, site_url: null, created_at: null },
  slack: { connected: slackConnected, expires_at: null, token_type: null, site_url: null, created_at: null },
  slack_settings: { leadership_channel_id: null },
});

describe('useSlackChannels', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: 0,
        },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  const wrapper = ({ children }: { children: React.ReactNode }): JSX.Element => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it('returns empty channels when Slack is not configured', async () => {
    vi.mocked(integrationsApi.getStatus).mockResolvedValue(makeStatus(false));

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
    });

    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
    expect(integrationsApi.getSlackChannels).not.toHaveBeenCalled();
  });

  it('fetches channels when Slack is configured', async () => {
    vi.mocked(integrationsApi.getStatus).mockResolvedValue(makeStatus(true));
    vi.mocked(integrationsApi.getSlackChannels).mockResolvedValue(mockSlackChannels);

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.channels.length).toBeGreaterThan(0);
    });

    expect(result.current.isSlackConfigured).toBe(true);
    expect(result.current.channels).toEqual(mockSlackChannels);
    expect(integrationsApi.getSlackChannels).toHaveBeenCalledTimes(1);
  });

  it('shows loading state while checking status', () => {
    vi.mocked(integrationsApi.getStatus).mockImplementation(
      () => new Promise(() => {})
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);
    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
  });

  it('shows loading state while fetching channels', async () => {
    vi.mocked(integrationsApi.getStatus).mockResolvedValue(makeStatus(true));
    vi.mocked(integrationsApi.getSlackChannels).mockImplementation(
      () => new Promise(() => {})
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
    });

    expect(result.current.isSlackConfigured).toBe(true);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.channels).toEqual([]);
  });

  it('returns default values when channels API returns empty array', async () => {
    vi.mocked(integrationsApi.getStatus).mockResolvedValue(makeStatus(true));
    vi.mocked(integrationsApi.getSlackChannels).mockResolvedValue([]);

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
      expect(result.current.isSlackConfigured).toBe(true);
    });

    expect(result.current.channels).toEqual([]);
    expect(result.current.isError).toBe(false);
  });
});
