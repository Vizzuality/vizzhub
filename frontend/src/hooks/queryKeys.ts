/**
 * Centralized query keys for React Query.
 *
 * Using typed constants prevents typos and makes refactoring easier.
 * All hooks should import keys from here instead of using string literals.
 */

export const queryKeys = {
  projects: {
    all: ['projects'] as const,
    detail: (id: string) => ['projects', id] as const,
  },
  metrics: {
    byProject: (projectId: string) => ['metrics', projectId] as const,
  },
  scores: {
    all: ['scores'] as const,
    byProject: (projectId: string) => ['scores', projectId] as const,
    history: (projectId: string, limit: number) =>
      ['scores', projectId, 'history', limit] as const,
  },
  config: {
    all: ['config'] as const,
    parameters: ['config', 'parameters'] as const,
    validation: ['config', 'validation'] as const,
  },
  snapshots: {
    byProject: (projectId: string) => ['snapshots', projectId] as const,
    detail: (projectId: string, year: number, month: number) =>
      ['snapshots', projectId, year, month] as const,
  },
} as const;
