import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import {
  useGlobalMetrics,
  useGlobalMetricsHistory,
  useAvailableGlobalMonths,
  useCalculateGlobalMetrics,
  useRecalculateGlobalMetrics,
} from '../useGlobalMetrics';
import { server } from '../../test/setup';
import { fixtures } from '../../test/msw-handlers';

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

describe('useGlobalMetrics', () => {
  describe('useGlobalMetrics', () => {
    it('fetches and returns global metrics for a specific month', async () => {
      const { result } = renderHook(() => useGlobalMetrics(2026, 1), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(fixtures.globalRecord);
    });

    it('returns null when no metrics exist for the month', async () => {
      server.use(
        http.get('/api/global/:year/:month', () => {
          return HttpResponse.json(null);
        }),
      );

      const { result } = renderHook(() => useGlobalMetrics(2020, 1), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toBeNull();
    });

    it('handles API errors', async () => {
      server.use(
        http.get('/api/global/:year/:month', () => {
          return HttpResponse.json(
            { detail: 'Network error' },
            { status: 500 },
          );
        }),
      );

      const { result } = renderHook(() => useGlobalMetrics(2024, 12), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useGlobalMetricsHistory', () => {
    it('fetches history with default limit', async () => {
      const { result } = renderHook(() => useGlobalMetricsHistory(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toHaveLength(3);
      expect(result.current.data![0]).toMatchObject({ year: 2026 });
    });

    it('fetches history with custom limit', async () => {
      server.use(
        http.get('/api/global/history', ({ request }) => {
          const url = new URL(request.url);
          const limit = Number(url.searchParams.get('limit') ?? '12');
          const records = Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
            ...fixtures.globalRecord,
            month: 1 + i,
          }));
          return HttpResponse.json({ records });
        }),
      );

      const { result } = renderHook(() => useGlobalMetricsHistory(6), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toHaveLength(3);
    });

    it('returns empty array when no history exists', async () => {
      server.use(
        http.get('/api/global/history', () => {
          return HttpResponse.json({ records: [] });
        }),
      );

      const { result } = renderHook(() => useGlobalMetricsHistory(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([]);
    });
  });

  describe('useAvailableGlobalMonths', () => {
    it('fetches available months', async () => {
      const { result } = renderHook(() => useAvailableGlobalMonths(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([
        { year: 2026, month: 1 },
        { year: 2025, month: 12 },
      ]);
    });

    it('returns empty array when no months available', async () => {
      server.use(
        http.get('/api/global/available-months', () => {
          return HttpResponse.json([]);
        }),
      );

      const { result } = renderHook(() => useAvailableGlobalMonths(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual([]);
    });
  });

  describe('useCalculateGlobalMetrics', () => {
    it('calculates global metrics for date range', async () => {
      let capturedBody: Record<string, unknown> | undefined;

      server.use(
        http.post('/api/global/calculate', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({
            year: 2026,
            month: 1,
            projects_processed: 5,
            record: fixtures.globalRecord,
          });
        }),
      );

      const { result } = renderHook(() => useCalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 10,
          to_year: 2024,
          to_month: 12,
        });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(capturedBody).toEqual({
        from_year: 2024,
        from_month: 10,
        to_year: 2024,
        to_month: 12,
      });
      expect(result.current.data).toMatchObject({ projects_processed: 5 });
    });

    it('handles calculation errors', async () => {
      server.use(
        http.post('/api/global/calculate', () => {
          return HttpResponse.json(
            { detail: 'Invalid date range' },
            { status: 400 },
          );
        }),
      );

      const { result } = renderHook(() => useCalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 12,
          to_year: 2024,
          to_month: 10,
        });
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useRecalculateGlobalMetrics', () => {
    it('recalculates global metrics for date range', async () => {
      let capturedBody: Record<string, unknown> | undefined;

      server.use(
        http.post('/api/global/recalculate', async ({ request }) => {
          capturedBody = await request.json() as Record<string, unknown>;
          return HttpResponse.json({
            year: 2026,
            month: 1,
            projects_processed: 5,
            record: fixtures.globalRecord,
          });
        }),
      );

      const { result } = renderHook(() => useRecalculateGlobalMetrics(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        result.current.mutate({
          from_year: 2024,
          from_month: 12,
          to_year: 2024,
          to_month: 12,
        });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(capturedBody).toEqual({
        from_year: 2024,
        from_month: 12,
        to_year: 2024,
        to_month: 12,
      });
      expect(result.current.data).toMatchObject({ projects_processed: 5 });
    });
  });
});
