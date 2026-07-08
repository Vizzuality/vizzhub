import { describe, it, expect } from 'vitest';
import { iterationStats, iterationSummary } from '../programs';
import type { ProjectIteration } from '../../types/portfolio';

function iter(overrides: Partial<ProjectIteration>): ProjectIteration {
  return {
    id: '1', name: 'X', status: 'live', start_year: 2021, end_year: 2022,
    has_scorecard: true, is_billable: true, is_absence: false,
    client_id: null, client_name: null,
    ...overrides,
  };
}

describe('iterationSummary', () => {
  it('counts active vs finished and shows the year range', () => {
    const s = iterationSummary([
      iter({ status: 'live', start_year: 2021, end_year: 2022 }),
      iter({ id: '2', status: 'finished', start_year: 2023, end_year: 2024 }),
    ]);
    expect(s).toBe('1 active · 1 finished · 2021–2024');
  });

  it('omits the range when no project has dates', () => {
    expect(iterationSummary([iter({ start_year: null, end_year: null })]))
      .toBe('1 active · 0 finished');
  });
});

describe('iterationStats', () => {
  it('returns structured counts and a null range without dates', () => {
    expect(iterationStats([iter({ status: 'finished', start_year: null, end_year: null })]))
      .toEqual({ active: 0, finished: 1, yearRange: null });
  });

  it('spans the range across all iterations', () => {
    const stats = iterationStats([
      iter({ start_year: 2019, end_year: 2020 }),
      iter({ id: '2', status: 'finished', start_year: 2023, end_year: 2026 }),
    ]);
    expect(stats).toEqual({ active: 1, finished: 1, yearRange: '2019–2026' });
  });
});
