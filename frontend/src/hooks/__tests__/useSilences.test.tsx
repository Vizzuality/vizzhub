import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSilences, useCreateSilence, useUpdateSilence, useDeleteSilence } from '../useSilences';
import { silencesApi } from '../../services/api';

vi.mock('../../services/api', () => ({
  silencesApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
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

describe('useSilences hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useSilences fetches active silences', async () => {
    const mockData = [
      {
        id: 1,
        project_id: 'proj-123',
        alert_definition_id: 1,
        silenced_until: '2024-02-01T00:00:00Z',
        reason: 'Testing',
        created_by: 'user-1',
        created_at: '2024-01-15T10:00:00Z',
        project_name: 'Test Project',
        alert_name: 'Budget Alert',
      },
    ];

    vi.mocked(silencesApi.list).mockResolvedValue(mockData);

    const { result } = renderHook(() => useSilences(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockData);
    expect(silencesApi.list).toHaveBeenCalledWith(undefined, false);
  });

  it('useSilences filters by project', async () => {
    vi.mocked(silencesApi.list).mockResolvedValue([]);

    const { result } = renderHook(() => useSilences('proj-123'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(silencesApi.list).toHaveBeenCalledWith('proj-123', false);
  });

  it('useCreateSilence creates a silence', async () => {
    const mockSilence = {
      id: 1,
      project_id: 'proj-123',
      alert_definition_id: null,
      silenced_until: null,
      reason: 'Testing',
      created_by: 'user-1',
      created_at: '2024-01-15T10:00:00Z',
      project_name: 'Test Project',
      alert_name: null,
    };

    vi.mocked(silencesApi.create).mockResolvedValue(mockSilence);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useCreateSilence(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        project_id: 'proj-123',
        alert_definition_id: null,
        silenced_until: null,
        reason: 'Testing',
      });
    });

    expect(silencesApi.create).toHaveBeenCalledWith({
      project_id: 'proj-123',
      alert_definition_id: null,
      silenced_until: null,
      reason: 'Testing',
    });
  });

  it('useUpdateSilence updates a silence', async () => {
    const mockSilence = {
      id: 1,
      project_id: 'proj-123',
      alert_definition_id: null,
      silenced_until: '2024-03-01T00:00:00Z',
      reason: 'Updated reason',
      created_by: 'user-1',
      created_at: '2024-01-15T10:00:00Z',
      project_name: 'Test Project',
      alert_name: null,
    };

    vi.mocked(silencesApi.update).mockResolvedValue(mockSilence);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateSilence(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        id: 1,
        data: {
          silenced_until: '2024-03-01T00:00:00Z',
          reason: 'Updated reason',
        },
      });
    });

    expect(silencesApi.update).toHaveBeenCalledWith(1, {
      silenced_until: '2024-03-01T00:00:00Z',
      reason: 'Updated reason',
    });
  });

  it('useDeleteSilence deletes a silence', async () => {
    vi.mocked(silencesApi.delete).mockResolvedValue();

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useDeleteSilence(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    expect(silencesApi.delete).toHaveBeenCalledWith(1);
  });
});
