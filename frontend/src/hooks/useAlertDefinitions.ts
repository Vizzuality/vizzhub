import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsAdminApi, scheduledJobsApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type {
  AlertDefinition,
  AlertDefinitionUpdate,
  AlertTestResponse,
  MessageTemplate,
  MessageTemplateUpdate,
  ScheduledJobInfo,
  JobTriggerResponse,
} from '../types';

/**
 * Hook for fetching alert definitions.
 */
export function useAlertDefinitions(): ReturnType<typeof useQuery<AlertDefinition[], Error>> {
  return useQuery({
    queryKey: queryKeys.alertDefinitions.all,
    queryFn: (): Promise<AlertDefinition[]> => alertsAdminApi.list(),
  });
}

/**
 * Hook for updating an alert definition.
 */
export function useUpdateAlertDefinition(): ReturnType<
  typeof useMutation<AlertDefinition, Error, { id: number; data: AlertDefinitionUpdate }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }): Promise<AlertDefinition> => alertsAdminApi.update(id, data),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.alertDefinitions.all });
    },
  });
}

/**
 * Hook for testing an alert (sends test notification).
 */
export function useTestAlert(): ReturnType<
  typeof useMutation<AlertTestResponse, Error, number>
> {
  return useMutation({
    mutationFn: (alertId: number): Promise<AlertTestResponse> => alertsAdminApi.test(alertId),
  });
}

/**
 * Hook for fetching message templates for an alert.
 */
export function useAlertTemplates(
  alertId: number | null,
): ReturnType<typeof useQuery<MessageTemplate[], Error>> {
  return useQuery({
    queryKey: queryKeys.alertDefinitions.templates(alertId ?? 0),
    queryFn: (): Promise<MessageTemplate[]> => alertsAdminApi.getTemplates(alertId!),
    enabled: alertId !== null,
  });
}

/**
 * Hook for updating a message template.
 */
export function useUpdateMessageTemplate(): ReturnType<
  typeof useMutation<MessageTemplate, Error, { templateId: number; data: MessageTemplateUpdate }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, data }): Promise<MessageTemplate> =>
      alertsAdminApi.updateTemplate(templateId, data),
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.alertDefinitions.all });
      queryClient.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] === 'alertDefinitions' && query.queryKey[2] === 'templates',
      });
    },
  });
}

/**
 * Hook for fetching scheduled jobs.
 */
export function useScheduledJobs(): ReturnType<typeof useQuery<ScheduledJobInfo[], Error>> {
  return useQuery({
    queryKey: queryKeys.scheduledJobs.all,
    queryFn: (): Promise<ScheduledJobInfo[]> => scheduledJobsApi.list(),
    refetchInterval: 30000,
  });
}

/**
 * Hook for manually triggering a scheduled job.
 */
export function useTriggerScheduledJob(): ReturnType<
  typeof useMutation<JobTriggerResponse, Error, string>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobName: string): Promise<JobTriggerResponse> => scheduledJobsApi.trigger(jobName),
    onSuccess: (): void => {
      const refetchAll = (): void => {
        queryClient.invalidateQueries({ queryKey: queryKeys.scheduledJobs.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
      };
      // Immediate invalidation
      refetchAll();
      // Delayed refetch to catch job completion (jobs typically complete in 1-3 seconds)
      setTimeout(refetchAll, 3000);
      setTimeout(refetchAll, 6000);
    },
  });
}
