import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { PlannerResponse } from '@/modules/capacity/types/planner';

const POLL_INTERVAL = 20_000;

export function usePlannerData(
  start: string,
  end: string,
  groupBy: string,
  flushPending?: () => Promise<void>,
): UseQueryResult<PlannerResponse> {
  const queryClient = useQueryClient();
  const lastUpdatedAt = useRef<string | null>(null);
  const flushRef = useRef(flushPending);
  flushRef.current = flushPending;

  const query = useQuery({
    queryKey: queryKeys.capacity.planner(start, end, groupBy),
    queryFn: () => plannerApi.get(start, end, groupBy),
  });

  useEffect(() => {
    if (!start || !end) return;

    const interval = setInterval(async () => {
      try {
        const { updated_at } = await plannerApi.getUpdatedAt(start, end);
        if (
          updated_at &&
          lastUpdatedAt.current &&
          updated_at > lastUpdatedAt.current
        ) {
          if (flushRef.current) await flushRef.current();
          queryClient.invalidateQueries({
            queryKey: queryKeys.capacity.planner(start, end, groupBy),
          });
        }
        lastUpdatedAt.current = updated_at;
      } catch {
        // Silently ignore polling errors
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [start, end, groupBy, queryClient]);

  useEffect(() => {
    if (query.dataUpdatedAt) {
      lastUpdatedAt.current = new Date().toISOString();
    }
  }, [query.dataUpdatedAt]);

  return query;
}
