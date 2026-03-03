import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { useNotifications, useNotificationStats } from '../useNotifications';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useNotifications hooks', () => {
  it('useNotifications fetches paginated notifications', async () => {
    const { result } = renderHook(() => useNotifications({ page: 1, page_size: 20 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(fixtures.paginatedNotifications);
  });

  it('useNotifications passes filters correctly', async () => {
    let capturedParams: Record<string, string> = {};
    server.use(
      http.get('/api/notifications', ({ request }) => {
        const url = new URL(request.url);
        capturedParams = Object.fromEntries(url.searchParams.entries());
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 10,
          pages: 0,
        });
      }),
    );

    const filters = {
      project_id: 'proj-123',
      alert_definition_id: 2,
      start_date: '2024-01-01',
      end_date: '2024-01-31',
      page: 1,
      page_size: 10,
    };

    const { result } = renderHook(() => useNotifications(filters), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedParams.project_id).toBe('proj-123');
    expect(capturedParams.alert_definition_id).toBe('2');
    expect(capturedParams.start_date).toBe('2024-01-01');
    expect(capturedParams.end_date).toBe('2024-01-31');
    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it('useNotificationStats fetches statistics', async () => {
    const { result } = renderHook(() => useNotificationStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual({ total: 10, unread: 3 });
  });

  it('useNotifications handles API errors', async () => {
    server.use(
      http.get('/api/notifications', () => {
        return HttpResponse.json(
          { detail: 'Internal Server Error' },
          { status: 500 },
        );
      }),
    );

    const { result } = renderHook(() => useNotifications(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});
