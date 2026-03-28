import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { JiraIssuesResponse } from '../types/tracker';

export function useJiraIssues(
  periodDate: string,
): UseQueryResult<JiraIssuesResponse> {
  return useQuery({
    queryKey: queryKeys.tracker.jiraIssues(periodDate),
    queryFn: () => trackerApi.getJiraIssues(periodDate),
    enabled: !!periodDate,
    staleTime: 5 * 60 * 1000,
  });
}
