import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useNotifications, useNotificationStats } from '../useNotifications';
import { notificationsApi } from '../../services/api';

vi.mock('../../services/api', () => ({
  notificationsApi: {
    list: vi.fn(),
    getStats: vi.fn(),
  },
}));

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useNotifications hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useNotifications fetches paginated notifications', async () => {
    const mockData = {
      items: [
        {
          id: 1,
          project_id: 'proj-123',
          alert_definition_id: 1,
          channel_id: 'C12345',
          message: 'Test alert',
          status: 'sent',
          error_message: null,
          metadata_json: null,
          sent_at: '2024-01-15T10:00:00Z',
          project_name: 'Test Project',
          alert_name: 'Budget Alert',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    };

    vi.mocked(notificationsApi.list).mockResolvedValue(mockData);

    const { result } = renderHook(() => useNotifications({ page: 1, page_size: 20 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(notificationsApi.list).toHaveBeenCalledWith({ page: 1, page_size: 20 });
  });

  it('useNotifications passes filters correctly', async () => {
    vi.mocked(notificationsApi.list).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    });

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

    expect(notificationsApi.list).toHaveBeenCalledWith(filters);
  });

  it('useNotificationStats fetches statistics', async () => {
    const mockData = {
      total_this_month: 15,
      by_type: {
        'Budget Alert': 5,
        'Timeline Alert': 10,
      },
      by_project: [
        { project_name: 'Project A', count: 8 },
        { project_name: 'Project B', count: 7 },
      ],
      avg_vulnerability_resolution_days: 3.5,
    };

    vi.mocked(notificationsApi.getStats).mockResolvedValue(mockData);

    const { result } = renderHook(() => useNotificationStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(notificationsApi.getStats).toHaveBeenCalled();
  });

  it('useNotifications handles API errors', async () => {
    vi.mocked(notificationsApi.list).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useNotifications(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toEqual(new Error('Network error'));
  });
});
