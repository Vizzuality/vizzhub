// Re-export all APIs from the api/ directory for backward compatibility
export { default } from '@/core/services/client';
export { projectsApi } from '@/core/services/projects';
export { configApi, scoresApi } from './api/scores';
export { captureApi, metricsHistoryApi } from './api/metrics';
export { jobsApi } from '@/core/services/jobs';
export { globalMetricsApi } from './api/global';
export {
  alertsAdminApi,
  notificationsApi,
  scheduledJobsApi,
  silencesApi,
} from '@/core/services/notifications';
export { exportsApi } from './api/exports';
export { isoApi } from './api/iso';
export type { ReviewListParams, SnapshotListParams } from './api/iso';
