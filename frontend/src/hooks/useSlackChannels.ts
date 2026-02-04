import { useQuery } from '@tanstack/react-query';
import { slackApi } from '../services/api';
import { queryKeys } from './queryKeys';
import { TIMING } from '../constants/timing';

export interface UseSlackChannelsResult {
  channels: import('../types').SlackChannel[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  isSlackConfigured: boolean;
  isCheckingStatus: boolean;
}

export function useSlackChannels(): UseSlackChannelsResult {
  const statusQuery = useQuery({
    queryKey: queryKeys.slack.status,
    queryFn: slackApi.getStatus,
    staleTime: TIMING.QUERY_STALE_TIME,
    retry: 1,
  });

  const channelsQuery = useQuery({
    queryKey: queryKeys.slack.channels,
    queryFn: slackApi.getChannels,
    enabled: statusQuery.data?.configured === true,
    staleTime: TIMING.QUERY_STALE_TIME,
    retry: 1,
  });

  const isSlackConfigured = statusQuery.data?.configured ?? false;

  return {
    channels: channelsQuery.data ?? [],
    isLoading: channelsQuery.isLoading && isSlackConfigured,
    isError: channelsQuery.isError || statusQuery.isError,
    error: channelsQuery.error ?? statusQuery.error ?? null,
    isSlackConfigured,
    isCheckingStatus: statusQuery.isLoading,
  };
}
