import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  useProjectScores,
  useScoreHistory,
  useScoringConfig,
} from '../useScores';
import { server } from '@/test/setup';
import { fixtures } from '@/test/msw-handlers';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useScores', () => {
  describe('useProjectScores', () => {
    it('fetches and returns project scores', async () => {
      const { result } = renderHook(() => useProjectScores('project-123'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toMatchObject({
        project_id: 'project-123',
        overall_score: 75.5,
      });
      expect(result.current.data?.scores?.dimensions).toBeDefined();
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useProjectScores(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
    });

    it('handles 404 when project has no metrics', async () => {
      server.use(
        http.get('/api/scores/project/:projectId', () => {
          return HttpResponse.json(
            { detail: 'No metrics found' },
            { status: 404 },
          );
        }),
      );

      const { result } = renderHook(
        () => useProjectScores('project-without-metrics'),
        { wrapper: createWrapper() },
      );

      await waitFor(() => expect(result.current.isError).toBe(true));
    });

    it('returns all dimension scores', async () => {
      const { result } = renderHook(() => useProjectScores('project-123'), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      const dimensions = result.current.data?.scores?.dimensions;
      expect(dimensions).toBeDefined();
      expect(Object.keys(dimensions!)).toHaveLength(8);
      expect(dimensions!.p_time).toBe(85);
      expect(dimensions!.p_quality).toBe(78);
    });
  });

  describe('useScoreHistory', () => {
    it('fetches score history with default limit', async () => {
      const { result } = renderHook(
        () => useScoreHistory('project-123'),
        { wrapper: createWrapper() },
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeDefined();
      expect(Array.isArray(result.current.data)).toBe(true);
      expect(result.current.data!.length).toBeGreaterThan(0);
    });

    it('fetches score history with custom limit', async () => {
      let capturedLimit: string | null = null;
      server.use(
        http.get('/api/scores/project/:projectId/history', ({ request }) => {
          const url = new URL(request.url);
          capturedLimit = url.searchParams.get('limit');
          const limit = Number(capturedLimit ?? '10');
          const history = Array.from({ length: limit }, (_, i) => ({
            ...fixtures.scores,
            scores: {
              ...fixtures.scores.scores,
              score: 70 + i,
            },
          }));
          return HttpResponse.json(history);
        }),
      );

      const limit = 5;
      const { result } = renderHook(
        () => useScoreHistory('project-123', limit),
        { wrapper: createWrapper() },
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toHaveLength(limit);
      expect(capturedLimit).toBe('5');
    });

    it('does not fetch when projectId is empty', () => {
      const { result } = renderHook(() => useScoreHistory(''), {
        wrapper: createWrapper(),
      });

      expect(result.current.isPending).toBe(true);
      expect(result.current.fetchStatus).toBe('idle');
    });
  });

  describe('useScoringConfig', () => {
    it('fetches and returns scoring configuration', async () => {
      const { result } = renderHook(() => useScoringConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(fixtures.config);
    });

    it('handles API errors', async () => {
      server.use(
        http.get('/api/config', () => {
          return HttpResponse.json(
            { detail: 'Config not found' },
            { status: 500 },
          );
        }),
      );

      const { result } = renderHook(() => useScoringConfig(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });
});
