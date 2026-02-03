import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSlackChannels } from '../useSlackChannels';
import { slackApi } from '../../services/api';
import type { SlackChannel } from '../../types';

vi.mock('../../services/api', () => ({
  slackApi: {
    getStatus: vi.fn(),
    getChannels: vi.fn(),
  },
}));

const mockSlackChannels: SlackChannel[] = [
  { id: 'C123', name: 'general', is_private: false },
  { id: 'C456', name: 'engineering', is_private: false },
];

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
    vi.mocked(slackApi.getStatus).mockResolvedValue({
      configured: false,
    });

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
    });

    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
    expect(slackApi.getChannels).not.toHaveBeenCalled();
  });

  it('fetches channels when Slack is configured', async () => {
    vi.mocked(slackApi.getStatus).mockResolvedValue({
      configured: true,
      channel_count: 2,
    });
    vi.mocked(slackApi.getChannels).mockResolvedValue(mockSlackChannels);

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.channels.length).toBeGreaterThan(0);
    });

    expect(result.current.isSlackConfigured).toBe(true);
    expect(result.current.channels).toEqual(mockSlackChannels);
    expect(slackApi.getChannels).toHaveBeenCalledTimes(1);
  });

  it('shows loading state while checking status', () => {
    vi.mocked(slackApi.getStatus).mockImplementation(
      () => new Promise(() => {})
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);
    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
  });

  it('shows loading state while fetching channels', async () => {
    vi.mocked(slackApi.getStatus).mockResolvedValue({
      configured: true,
      channel_count: 2,
    });
    vi.mocked(slackApi.getChannels).mockImplementation(
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
    vi.mocked(slackApi.getStatus).mockResolvedValue({
      configured: true,
      channel_count: 0,
    });
    vi.mocked(slackApi.getChannels).mockResolvedValue([]);

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
      expect(result.current.isSlackConfigured).toBe(true);
    });

    expect(result.current.channels).toEqual([]);
    expect(result.current.isError).toBe(false);
  });
});
