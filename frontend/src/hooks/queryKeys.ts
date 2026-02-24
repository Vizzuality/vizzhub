/**
 * Centralized query keys for React Query.
 *
 * Using typed constants prevents typos and makes refactoring easier.
 * All hooks should import keys from here instead of using string literals.
 */

import type { ProjectListParams } from '../types';

export const queryKeys = {
  projects: {
    all: ['projects'] as const,
    list: (params: ProjectListParams) => ['projects', 'list', params] as const,
    summary: ['projects', 'summary'] as const,
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
  slack: {
    status: ['slack', 'status'] as const,
    channels: ['slack', 'channels'] as const,
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
    config: ['iso', 'config'] as const,
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
} as const;
