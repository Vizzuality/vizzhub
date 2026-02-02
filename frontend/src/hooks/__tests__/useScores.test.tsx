import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useProjectScores,
  useScoreHistory,
  useScoringConfig,
} from '../useScores';
import { scoresApi, configApi } from '../../services/api';

vi.mock('../../services/api', () => ({
  scoresApi: {
    getProjectScores: vi.fn(),
    getScoreHistory: vi.fn(),
  },
  configApi: {
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

describe('useScores', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useProjectScores', () => {
    it('fetches and returns project scores', async () => {
      const projectId = 'project-123';
      const mockScores = {
        project_id: projectId,
        overall_score: 75.5,
        dimension_scores: {
          P_time: 80,
          P_cost: 75,
          P_quality: 70,
          P_value: 85,
          P_satisfaction: 90,
          P_flow: 65,
          P_engineering: 78,
          P_risk: 82,
        },
        indicators: {},
        metadata: {},
      };

      vi.mocked(scoresApi.getProjectScores).mockResolvedValue(mockScores);

      const { result } = renderHook(() => useProjectScores(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockScores);
      expect(scoresApi.getProjectScores).toHaveBeenCalledWith(projectId, undefined, undefined);
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useProjectScores(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
      expect(scoresApi.getProjectScores).not.toHaveBeenCalled();
    });

    it('handles 404 when project has no metrics', async () => {
      const projectId = 'project-without-metrics';

      vi.mocked(scoresApi.getProjectScores).mockRejectedValue({
        response: { status: 404 },
      });

      const { result } = renderHook(() => useProjectScores(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });

    it('returns all dimension scores', async () => {
      const projectId = 'project-123';
      const mockScores = {
        project_id: projectId,
        overall_score: 75.5,
        dimension_scores: {
          P_time: 80,
          P_cost: 75,
          P_quality: 70,
          P_value: 85,
          P_satisfaction: 90,
          P_flow: 65,
          P_engineering: 78,
          P_risk: 82,
        },
      };

      vi.mocked(scoresApi.getProjectScores).mockResolvedValue(mockScores);

      const { result } = renderHook(() => useProjectScores(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const scores = result.current.data?.dimension_scores;
      expect(Object.keys(scores || {})).toHaveLength(8);
      expect(scores?.P_time).toBe(80);
      expect(scores?.P_quality).toBe(70);
    });
  });

  describe('useScoreHistory', () => {
    it('fetches score history with default limit', async () => {
      const projectId = 'project-123';
      const mockHistory = [
        {
          date: '2026-01-31',
          overall_score: 75.5,
          dimension_scores: { P_time: 80 },
        },
        {
          date: '2025-12-31',
          overall_score: 72,
          dimension_scores: { P_time: 78 },
        },
      ];

      vi.mocked(scoresApi.getScoreHistory).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useScoreHistory(projectId), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockHistory);
      expect(scoresApi.getScoreHistory).toHaveBeenCalledWith(projectId, 10);
    });

    it('fetches score history with custom limit', async () => {
      const projectId = 'project-123';
      const limit = 5;
      const mockHistory = Array.from({ length: limit }, (_, i) => ({
        date: `2026-01-${31 - i}`,
        overall_score: 70 + i,
        dimension_scores: {},
      }));

      vi.mocked(scoresApi.getScoreHistory).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useScoreHistory(projectId, limit), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toHaveLength(limit);
      expect(scoresApi.getScoreHistory).toHaveBeenCalledWith(projectId, limit);
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useScoreHistory(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
      expect(scoresApi.getScoreHistory).not.toHaveBeenCalled();
    });
  });

  describe('useScoringConfig', () => {
    it('fetches and returns scoring configuration', async () => {
      const mockConfig = {
        targets: {
          defect_density: 3,
          escaped_rate: 0.01,
          lead_time_days: 5,
        },
        weights: {
          global: {
            time: 0.12,
            cost: 0.1,
            quality: 0.18,
            value: 0.15,
            satisfaction: 0.12,
            flow: 0.15,
            engineering: 0.1,
            risk: 0.08,
          },
        },
        constants: {
          sev1_cap: 60,
          milestone_grace_days: 3,
        },
      };

      vi.mocked(configApi.get).mockResolvedValue(mockConfig);

      const { result } = renderHook(() => useScoringConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockConfig);
      expect(configApi.get).toHaveBeenCalledTimes(1);
    });

    it('handles API errors', async () => {
      vi.mocked(configApi.get).mockRejectedValue(new Error('Config not found'));

      const { result } = renderHook(() => useScoringConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

});
