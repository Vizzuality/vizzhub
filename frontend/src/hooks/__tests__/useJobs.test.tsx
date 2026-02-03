import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useJobStatus,
  useCaptureHistoryJob,
  useProjectJobs,
  useAllJobs,
  useCancelJob,
  useDeleteJob,
} from '../useJobs';
import { jobsApi } from '../../services/api';
import type {
  JobDetailResponse,
  JobResponse,
  JobSummaryResponse,
} from '../../types';

vi.mock('../../services/api', () => ({
  jobsApi: {
    getJob: vi.fn(),
    createCaptureHistory: vi.fn(),
    listJobs: vi.fn(),
    cancelJob: vi.fn(),
    deleteJob: vi.fn(),
  },
}));

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

const mockJobDetail: JobDetailResponse = {
  id: 'job-123',
  project_id: 'proj-456',
  type: 'capture_history',
  status: 'running',
  progress: 50,
  message: 'Processing month 6 of 12',
  parameters: {
    start_year: 2024,
    start_month: 1,
    end_year: 2024,
    end_month: 12,
  },
  created_at: '2024-12-01T10:00:00Z',
  started_at: '2024-12-01T10:00:01Z',
  completed_at: null,
};

const mockJobResponse: JobResponse = {
  id: 'job-123',
  status: 'pending',
  message: 'Job created',
};

const mockJobSummary: JobSummaryResponse = {
  id: 'job-123',
  project_id: 'proj-456',
  type: 'capture_history',
  status: 'completed',
  progress: 100,
  message: 'Completed',
  created_at: '2024-12-01T10:00:00Z',
};

describe('useJobs hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useJobStatus', () => {
    it('fetches job status when jobId is provided', async () => {
      vi.mocked(jobsApi.getJob).mockResolvedValue(mockJobDetail);

      const { result } = renderHook(() => useJobStatus('job-123'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(jobsApi.getJob).toHaveBeenCalledWith('job-123');
      expect(result.current.data).toEqual(mockJobDetail);
    });

    it('does not fetch when jobId is null', async () => {
      const { result } = renderHook(() => useJobStatus(null), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
      expect(jobsApi.getJob).not.toHaveBeenCalled();
    });

    it('does not fetch when enabled is false', async () => {
      const { result } = renderHook(
        () => useJobStatus('job-123', { enabled: false }),
        { wrapper: createWrapper() },
      );

      expect(result.current.isLoading).toBe(false);
      expect(jobsApi.getJob).not.toHaveBeenCalled();
    });
  });

  describe('useCaptureHistoryJob', () => {
    it('creates a capture history job', async () => {
      vi.mocked(jobsApi.createCaptureHistory).mockResolvedValue(mockJobResponse);

      const { result } = renderHook(() => useCaptureHistoryJob('proj-456'), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync({
          start_year: 2024,
          start_month: 1,
          end_year: 2024,
          end_month: 12,
        });
      });

      expect(jobsApi.createCaptureHistory).toHaveBeenCalledWith({
        project_id: 'proj-456',
        start_year: 2024,
        start_month: 1,
        end_year: 2024,
        end_month: 12,
      });
    });
  });

  describe('useProjectJobs', () => {
    it('lists jobs for a project', async () => {
      vi.mocked(jobsApi.listJobs).mockResolvedValue([mockJobSummary]);

      const { result } = renderHook(() => useProjectJobs('proj-456'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(jobsApi.listJobs).toHaveBeenCalledWith('proj-456');
      expect(result.current.data).toEqual([mockJobSummary]);
    });
  });

  describe('useAllJobs', () => {
    it('lists all jobs', async () => {
      vi.mocked(jobsApi.listJobs).mockResolvedValue([mockJobSummary]);

      const { result } = renderHook(() => useAllJobs(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(jobsApi.listJobs).toHaveBeenCalledWith();
      expect(result.current.data).toEqual([mockJobSummary]);
    });
  });

  describe('useCancelJob', () => {
    it('cancels a job', async () => {
      const cancelledJob: JobResponse = { ...mockJobResponse, status: 'cancelled' };
      vi.mocked(jobsApi.cancelJob).mockResolvedValue(cancelledJob);

      const { result } = renderHook(() => useCancelJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync('job-123');
      });

      expect(jobsApi.cancelJob).toHaveBeenCalledWith('job-123');
    });
  });

  describe('useDeleteJob', () => {
    it('deletes a job', async () => {
      vi.mocked(jobsApi.deleteJob).mockResolvedValue();

      const { result } = renderHook(() => useDeleteJob(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.mutateAsync('job-123');
      });

      expect(jobsApi.deleteJob).toHaveBeenCalledWith('job-123');
    });
  });
});
