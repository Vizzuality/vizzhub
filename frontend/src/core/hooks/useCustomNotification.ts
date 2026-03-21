import { useMutation } from '@tanstack/react-query';
import { alertsAdminApi } from '@/core/services/notifications';
import type { CustomNotificationRequest, CustomNotificationResponse } from '@/types';

/**
 * Hook for sending a custom Slack notification.
 */
export function useSendCustomNotification(): ReturnType<
  typeof useMutation<CustomNotificationResponse, Error, CustomNotificationRequest>
> {
  return useMutation({
    mutationFn: (data: CustomNotificationRequest): Promise<CustomNotificationResponse> =>
      alertsAdminApi.sendCustom(data),
  });
}
