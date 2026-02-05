// Re-export all APIs from the api/ directory for backward compatibility
export { default } from './api/client';
export { projectsApi } from './api/projects';
export { configApi, scoresApi } from './api/scores';
export { captureApi, collectApi, metricsHistoryApi, snapshotsApi } from './api/metrics';
export { jobsApi } from './api/jobs';
export { globalMetricsApi } from './api/global';
export { slackApi } from './api/slack';
export type { SlackConfigResponse, SlackStatusResponse, SlackTestResult } from './api/slack';
export {
  alertsAdminApi,
  notificationsApi,
  scheduledJobsApi,
  silencesApi,
} from './api/notifications';
export { exportsApi } from './api/exports';
