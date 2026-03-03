/**
 * Centralized timing constants for the application.
 *
 * Using constants prevents magic numbers scattered throughout the codebase
 * and makes it easy to adjust timing values in one place.
 */
export const TIMING = {
  /** Polling interval for active job status (pending/running) */
  JOB_POLLING_ACTIVE: 3000,
  /** Polling interval for job list refresh */
  JOB_POLLING_ALL: 5000,
  /** Polling interval for scheduled jobs list */
  SCHEDULED_JOBS_POLLING: 30000,
  /** Default stale time for React Query cache */
  QUERY_STALE_TIME: 5 * 60 * 1000,
  /** Timeout for GitHub API calls */
  API_TIMEOUT_GITHUB: 60000,
  /** Timeout for capture period API calls */
  API_TIMEOUT_CAPTURE: 120000,
  /** Duration to show notification/test results before auto-dismiss */
  NOTIFICATION_DISMISS: 5000,
  /** Duration to show brief success/error messages */
  MESSAGE_DISMISS: 3000,
  /** Delay before refetching after job trigger (jobs complete in 1-3s) */
  JOB_TRIGGER_REFETCH_DELAY: 3000,
  /** Secondary delay for job trigger refetch */
  JOB_TRIGGER_REFETCH_DELAY_SECONDARY: 6000,
} as const;
