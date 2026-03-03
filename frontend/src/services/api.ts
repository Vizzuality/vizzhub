// Re-export all APIs from the api/ directory for backward compatibility
export { default } from '@/core/services/client';
export { projectsApi } from '@/core/services/projects';
export { configApi, scoresApi } from '@/modules/scorecard/services/scores';
export { captureApi, metricsHistoryApi } from '@/modules/scorecard/services/metrics';
export { jobsApi } from '@/core/services/jobs';
export { globalMetricsApi } from '@/modules/scorecard/services/global';
export {
  alertsAdminApi,
  notificationsApi,
  scheduledJobsApi,
  silencesApi,
} from '@/core/services/notifications';
export { exportsApi } from '@/modules/scorecard/services/exports';
export { isoApi } from './api/iso';
export type { ReviewListParams, SnapshotListParams } from './api/iso';
