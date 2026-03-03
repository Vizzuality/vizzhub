// Re-export the axios client as default
export { default } from '@/core/services/client';
export { default as api } from '@/core/services/client';

// Project API
export { projectsApi } from '@/core/services/projects';

// Scores and Config API
export { configApi, scoresApi } from '@/modules/scorecard/services/scores';

// Metrics API
export { captureApi, metricsHistoryApi } from '@/modules/scorecard/services/metrics';

// Jobs API
export { jobsApi } from '@/core/services/jobs';

// Global Metrics API
export { globalMetricsApi } from '@/modules/scorecard/services/global';

// Notifications API
export {
  alertsAdminApi,
  notificationsApi,
  scheduledJobsApi,
  silencesApi,
} from '@/core/services/notifications';

// Exports API
export { exportsApi } from '@/modules/scorecard/services/exports';

// ISO API
export { isoApi } from '@/modules/iso/services/iso';
export type { ReviewListParams, SnapshotListParams } from '@/modules/iso/services/iso';
