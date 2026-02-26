// Re-export the axios client as default
export { default } from './client';
export { default as api } from './client';

// Project API
export { projectsApi } from './projects';

// Scores and Config API
export { configApi, scoresApi } from './scores';

// Metrics API
export { captureApi, metricsHistoryApi } from './metrics';

// Jobs API
export { jobsApi } from './jobs';

// Global Metrics API
export { globalMetricsApi } from './global';

// Notifications API
export {
  alertsAdminApi,
  notificationsApi,
  scheduledJobsApi,
  silencesApi,
} from './notifications';

// Exports API
export { exportsApi } from './exports';

// ISO API
export { isoApi } from './iso';
export type { ReviewListParams, SnapshotListParams } from './iso';
