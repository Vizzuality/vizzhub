import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { useSlackChannels } from '../useSlackChannels';
import { server } from '../../test/setup';
import { fixtures } from '../../test/msw-handlers';

describe('useSlackChannels', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
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
    server.use(
      http.get('/api/admin/integrations/status', () => {
        return HttpResponse.json({
          ...fixtures.integrationsStatus,
          slack: { ...fixtures.integrationsStatus.slack, connected: false },
        });
      }),
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
    });

    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
  });

  it('fetches channels when Slack is configured', async () => {
    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.channels.length).toBeGreaterThan(0);
    });

    expect(result.current.isSlackConfigured).toBe(true);
    expect(result.current.channels).toEqual(fixtures.slackChannels);
  });

  it('shows loading state while checking status', () => {
    server.use(
      http.get('/api/admin/integrations/status', () => {
        return new Promise(() => {});
      }),
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    expect(result.current.isCheckingStatus).toBe(true);
    expect(result.current.isSlackConfigured).toBe(false);
    expect(result.current.channels).toEqual([]);
  });

  it('shows loading state while fetching channels', async () => {
    server.use(
      http.get('/api/admin/integrations/slack/channels', () => {
        return new Promise(() => {});
      }),
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
    server.use(
      http.get('/api/admin/integrations/slack/channels', () => {
        return HttpResponse.json([]);
      }),
    );

    const { result } = renderHook(() => useSlackChannels(), { wrapper });

    await waitFor(() => {
      expect(result.current.isCheckingStatus).toBe(false);
      expect(result.current.isSlackConfigured).toBe(true);
    });

    expect(result.current.channels).toEqual([]);
    expect(result.current.isError).toBe(false);
  });
});
