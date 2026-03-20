/**
 * Centralized query keys for React Query.
 *
 * Using typed constants prevents typos and makes refactoring easier.
 * All hooks should import keys from here instead of using string literals.
 */

import type { ProjectListParams } from '@/types';

export const queryKeys = {
  projects: {
    all: ['projects'] as const,
    list: (params: ProjectListParams) => ['projects', 'list', params] as const,
    scorecardList: (params: ProjectListParams) => ['projects', 'scorecard-list', params] as const,
    summary: ['projects', 'summary'] as const,
    allSummary: ['projects', 'all-summary'] as const,
    activeSummary: ['projects', 'active-summary'] as const,
    scorecardSummary: ['projects', 'scorecard-summary'] as const,
    detail: (id: string) => ['projects', id] as const,
  },
  metrics: {
    byProject: (projectId: string) => ['metrics', projectId] as const,
    byPeriod: (projectId: string, year: number, month: number) =>
      ['metrics', projectId, year, month] as const,
  },
  scores: {
    all: ['scores'] as const,
    byProject: (projectId: string) => ['scores', projectId] as const,
    byPeriod: (projectId: string, year: number, month: number) =>
      ['scores', projectId, year, month] as const,
    history: (projectId: string, limit: number) =>
      ['scores', projectId, 'history', limit] as const,
    batch: (ids: string[]) => ['scores', 'batch', ...[...ids].sort((a, b) => a.localeCompare(b))] as const,
  },
  config: {
    all: ['config'] as const,
    parameters: ['config', 'parameters'] as const,
    validation: ['config', 'validation'] as const,
  },
  snapshots: {
    byProject: (projectId: string) => ['snapshots', projectId] as const,
    history: (projectId: string, limit: number) =>
      ['snapshots', projectId, 'history', limit] as const,
    detail: (projectId: string, year: number, month: number) =>
      ['snapshots', projectId, year, month] as const,
  },
  jobs: {
    all: ['jobs'] as const,
    byProject: (projectId: string) => ['jobs', 'project', projectId] as const,
    detail: (jobId: string) => ['jobs', 'detail', jobId] as const,
  },
  global: {
    all: ['global'] as const,
    record: (year: number, month: number) => ['global', 'record', year, month] as const,
    history: (limit?: number) => ['global', 'history', limit] as const,
    availableMonths: ['global', 'available-months'] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    list: (filters: {
      project_id?: string;
      alert_definition_id?: number;
      start_date?: string;
      end_date?: string;
      page?: number;
      page_size?: number;
    }) => ['notifications', 'list', filters] as const,
    stats: ['notifications', 'stats'] as const,
  },
  silences: {
    all: ['silences'] as const,
    list: (projectId?: string) => ['silences', 'list', projectId] as const,
  },
  alertDefinitions: {
    all: ['alertDefinitions'] as const,
    templates: (alertId: number) => ['alertDefinitions', alertId, 'templates'] as const,
  },
  scheduledJobs: {
    all: ['scheduledJobs'] as const,
  },
  users: {
    all: ['users'] as const,
    detail: (id: string) => ['users', id] as const,
  },
  iso: {
    config: {
      all: ['iso', 'config'] as const,
      googleWorkspace: ['iso', 'config', 'googleWorkspace'] as const,
      github: ['iso', 'config', 'github'] as const,
      jira: ['iso', 'config', 'jira'] as const,
    },
    snapshots: {
      all: ['iso', 'snapshots'] as const,
      list: (params: { provider?: string; page?: number; page_size?: number }) =>
        ['iso', 'snapshots', 'list', params] as const,
      detail: (id: string) => ['iso', 'snapshots', id] as const,
    },
    reviews: {
      all: ['iso', 'reviews'] as const,
      list: (params: { status?: string; page?: number; page_size?: number }) =>
        ['iso', 'reviews', 'list', params] as const,
      detail: (id: string) => ['iso', 'reviews', id] as const,
      bySnapshot: (snapshotId: string) =>
        ['iso', 'reviews', 'bySnapshot', snapshotId] as const,
    },
  },
  programs: {
    all: ['programs'] as const,
    list: ['programs', 'list'] as const,
  },
  functionalAreas: {
    all: ['functionalAreas'] as const,
  },
  integrations: {
    status: ['integrations', 'status'] as const,
    slackChannels: ['integrations', 'slack', 'channels'] as const,
  },
  tracker: {
    periods: {
      all: ['tracker', 'periods'] as const,
      list: () => ['tracker', 'periods', 'list'] as const,
      detail: (id: string) => ['tracker', 'periods', id] as const,
    },
    reports: {
      all: ['tracker', 'reports'] as const,
      byPeriod: (periodId: string) =>
        ['tracker', 'reports', 'period', periodId] as const,
      detail: (id: string) => ['tracker', 'reports', id] as const,
    },
    costs: {
      batch: (ids: string[]) =>
        ['tracker', 'costs', 'batch', ...[...ids].sort((a, b) => a.localeCompare(b))] as const,
    },
    budgetLines: {
      byProject: (projectId: string) =>
        ['tracker', 'budget-lines', projectId] as const,
    },
    progress: {
      byProject: (projectId: string) =>
        ['tracker', 'progress', projectId] as const,
      batch: (ids: string[]) =>
        ['tracker', 'progress', 'batch', ...[...ids].sort((a, b) => a.localeCompare(b))] as const,
    },
    invoices: {
      byProject: (projectId: string) =>
        ['tracker', 'invoices', projectId] as const,
      all: (params: Record<string, unknown>) =>
        ['tracker', 'invoices', 'all', params] as const,
    },
    nonStaffCosts: {
      byProject: (projectId: string) =>
        ['tracker', 'non-staff-costs', projectId] as const,
    },
    projectCosts: {
      summary: (projectId: string) =>
        ['tracker', 'project-costs', projectId, 'summary'] as const,
      parts: (projectId: string, periodId?: string) =>
        ['tracker', 'project-costs', projectId, 'parts', periodId] as const,
      aggregations: (projectId: string, groupBy: string) =>
        ['tracker', 'project-costs', projectId, 'aggregations', groupBy] as const,
    },
  },
} as const;
