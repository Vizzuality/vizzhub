import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useProjectMetrics } from '../useMetrics';
import api from '../../services/api';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useProjectMetrics', () => {
    it('fetches and returns project metrics', async () => {
      const projectId = 'project-123';
      const mockMetrics = {
        id: 'metrics-1',
        project_id: projectId,
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        tasks_completed: 50,
        tasks_in_progress: 10,
        defects_found: 5,
        defects_escaped: 1,
        created_at: '2026-01-31T12:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue({ data: [mockMetrics] });

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockMetrics);
      expect(api.get).toHaveBeenCalledWith(`/metrics/project/${projectId}`);
    });

    it('returns null when no metrics found (404)', async () => {
      const projectId = 'project-without-metrics';

      vi.mocked(api.get).mockRejectedValue({
        response: { status: 404 },
      });

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useProjectMetrics(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
      expect(api.get).not.toHaveBeenCalled();
    });

    it('handles API errors gracefully', async () => {
      const projectId = 'project-123';

      vi.mocked(api.get).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('handles metrics with EVM data', async () => {
      const projectId = 'project-123';
      const mockMetrics = {
        id: 'metrics-1',
        project_id: projectId,
        period_start: '2026-01-01',
        period_end: '2026-01-31',
        tasks_completed: 50,
        evm_data: {
          budget_total: 100000,
          budget_spent: 80000,
          earned_value: 75000,
        },
        created_at: '2026-01-31T12:00:00Z',
      };

      vi.mocked(api.get).mockResolvedValue({ data: [mockMetrics] });

      const { result } = renderHook(() => useProjectMetrics(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data?.evm_data).toBeDefined();
      expect(result.current.data?.evm_data?.budget_total).toBe(100000);
    });
  });
});
