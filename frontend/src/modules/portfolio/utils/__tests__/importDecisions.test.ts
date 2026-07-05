import { describe, expect, it } from 'vitest';
import { mergePrograms, seedDecisions } from '../importDecisions';
import type { OverviewMatch } from '../../types/portfolio';

function makeMatch(overrides: Partial<OverviewMatch>): OverviewMatch {
  return {
    staging_id: 's1',
    name: 'Global Forest Watch',
    is_old_project: false,
    client_type_raw: null,
    service_raw: null,
    impact_area_raw: null,
    suggested_project: { project_id: null, score: 0 },
    project_candidates: [],
    current_program: { program_id: null, name: null },
    program_candidates: [],
    suggested_program: { program_id: null, score: 0 },
    ...overrides,
  };
}

describe('seedDecisions (program-first default)', () => {
  it('links the fuzzy-matched program with no project anchor', () => {
    const d = seedDecisions([
      makeMatch({ suggested_program: { program_id: 'prog-1', score: 0.9 } }),
    ]).s1;
    expect(d.project_id).toBeNull();
    expect(d.program_action).toBe('link');
    expect(d.program_id).toBe('prog-1');
  });

  it('creates a program from the row name when no program matches', () => {
    const d = seedDecisions([makeMatch({ name: 'Marxan' })]).s1;
    expect(d.project_id).toBeNull();
    expect(d.program_action).toBe('create');
    expect(d.new_program_name).toBe('Marxan');
  });

  it('never pre-selects a project even when a strong project candidate exists', () => {
    const d = seedDecisions([
      makeMatch({ project_candidates: [{ id: 'proj-1', name: 'GFW 2023', score: 0.95 }] }),
    ]).s1;
    expect(d.project_id).toBeNull();
  });
});

describe('mergePrograms', () => {
  it('puts candidates first and dedupes the full list by id', () => {
    const merged = mergePrograms(
      [{ id: 'a', name: 'Alpha' }],
      [
        { id: 'b', name: 'Beta' },
        { id: 'a', name: 'Alpha dup' },
      ],
    );
    expect(merged.map((p) => p.id)).toEqual(['a', 'b']);
  });
});
