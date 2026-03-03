import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  useJobStatus,
  useCaptureHistoryJob,
  useProjectJobs,
  useAllJobs,
  useCancelJob,
  useDeleteJob,
} from '../useJobs';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

function createWrapper(): ({ children }: { children: React.ReactNode }) => JSX.Element {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useJobs hooks', () => {
  describe('useJobStatus', () => {
    it('fetches job status when jobId is provided', async () => {
      const { result } = renderHook(() => useJobStatus('job-123'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toMatchObject({ id: 'job-123' });
    });

    it('does not fetch when jobId is null', async () => {
      const { result } = renderHook(() => useJobStatus(null), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
      expect(result.current.fetchStatus).toBe('idle');
    });

    it('does not fetch when enabled is false', async () => {
      const { result } = renderHook(
        () => useJobStatus('job-123', { enabled: false }),
        { wrapper: createWrapper() },
      );

      expect(result.current.isLoading).toBe(false);
      expect(result.current.fetchStatus).toBe('idle');
    });
  });

  describe('useCaptureHistoryJob', () => {
    it('creates a capture history job with project_id', async () => {
      let capturedBody: unknown;
      server.use(
        http.post('/api/jobs/capture-history', async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json({
            ...fixtures.job,
            id: 'new-job-id',
            status: 'pending',
          });
        }),
      );

      const { result } = renderHook(() => useCaptureHistoryJob('proj-456'), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync({
          from_year: 2024,
          from_month: 1,
          to_year: 2024,
          to_month: 12,
        });
      });

      expect(capturedBody).toEqual({
        project_id: 'proj-456',
        from_year: 2024,
        from_month: 1,
        to_year: 2024,
        to_month: 12,
      });
    });
  });

  describe('useProjectJobs', () => {
    it('lists jobs for a project', async () => {
      server.use(
        http.get('/api/jobs', ({ request }) => {
          const url = new URL(request.url);
          const projectId = url.searchParams.get('project_id');
          if (projectId === 'proj-456') {
            return HttpResponse.json([
              { ...fixtures.job, project_id: 'proj-456' },
            ]);
          }
          return HttpResponse.json([]);
        }),
      );

      const { result } = renderHook(() => useProjectJobs('proj-456'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(1);
      expect(result.current.data![0].project_id).toBe('proj-456');
    });
  });

  describe('useAllJobs', () => {
    it('lists all jobs', async () => {
      const { result } = renderHook(() => useAllJobs(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual([fixtures.job]);
    });
  });

  describe('useCancelJob', () => {
    it('cancels a job', async () => {
      const { result } = renderHook(() => useCancelJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        const response = await result.current.mutateAsync('job-123');
        expect(response).toMatchObject({ id: 'job-123', status: 'cancelled' });
      });
    });
  });

  describe('useDeleteJob', () => {
    it('deletes a job', async () => {
      const { result } = renderHook(() => useDeleteJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync('job-123');
      });

      expect(result.current.isSuccess).toBe(true);
    });
  });
});
