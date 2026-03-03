import { useQuery } from '@tanstack/react-query';
import { notificationsApi } from '@/services/api';
import { queryKeys } from './queryKeys';
import type { NotificationFilters, NotificationStats, PaginatedNotifications } from '@/types';

/**
 * Hook for fetching paginated notification logs.
 */
export function useNotifications(
  filters: NotificationFilters = {},
): ReturnType<typeof useQuery<PaginatedNotifications, Error>> {
  return useQuery({
    queryKey: queryKeys.notifications.list(filters),
    queryFn: (): Promise<PaginatedNotifications> => notificationsApi.list(filters),
  });
}

/**
 * Hook for fetching notification statistics.
 */
export function useNotificationStats(): ReturnType<typeof useQuery<NotificationStats, Error>> {
  return useQuery({
    queryKey: queryKeys.notifications.stats,
    queryFn: (): Promise<NotificationStats> => notificationsApi.getStats(),
  });
}
