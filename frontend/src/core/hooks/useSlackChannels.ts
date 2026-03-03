import { useQuery } from '@tanstack/react-query';
import { integrationsApi } from '@/core/services/integrations';
import { queryKeys } from './queryKeys';
import { TIMING } from '@/constants/timing';
import type { SlackChannel } from '@/types';

export interface UseSlackChannelsResult {
  channels: SlackChannel[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  isSlackConfigured: boolean;
  isCheckingStatus: boolean;
}

export function useSlackChannels(): UseSlackChannelsResult {
  const statusQuery = useQuery({
    queryKey: queryKeys.integrations.status,
    queryFn: integrationsApi.getStatus,
    staleTime: TIMING.QUERY_STALE_TIME,
    retry: 1,
  });

  const isSlackConfigured = statusQuery.data?.slack?.connected ?? false;

  const channelsQuery = useQuery({
    queryKey: queryKeys.integrations.slackChannels,
    queryFn: integrationsApi.getSlackChannels,
    enabled: isSlackConfigured,
    staleTime: TIMING.QUERY_STALE_TIME,
    retry: 1,
  });

  return {
    channels: channelsQuery.data ?? [],
    isLoading: channelsQuery.isLoading && isSlackConfigured,
    isError: channelsQuery.isError || statusQuery.isError,
    error: channelsQuery.error ?? statusQuery.error ?? null,
    isSlackConfigured,
    isCheckingStatus: statusQuery.isLoading,
  };
}
