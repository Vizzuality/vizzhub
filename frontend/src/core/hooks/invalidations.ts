import type { QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';

/**
 * Invalidate integrations caches after a Slack/GitHub/etc. credential change.
 *
 * Centralised because three sites mutate integration state (`SlackTab`,
 * `GitHubCard`, future provider tabs) and inconsistent invalidations cause
 * "saved but didn't update" UI bugs.
 */
export function invalidateIntegrations(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
  queryClient.invalidateQueries({ queryKey: queryKeys.integrations.slackChannels });
}
