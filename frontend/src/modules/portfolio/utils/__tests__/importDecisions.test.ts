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
    saved_decision: null,
    ...overrides,
  };
}

describe('seedDecisions (re-hydrates from saved_decision)', () => {
  it('reads the persisted LINK decision', () => {
    const d = seedDecisions([
      makeMatch({
        saved_decision: {
          project_id: null,
          program_action: 'link',
          program_id: 'prog-1',
          new_program_name: null,
        },
      }),
    ]).s1;
    expect(d.project_id).toBeNull();
    expect(d.program_action).toBe('link');
    expect(d.program_id).toBe('prog-1');
  });

  it('reads the persisted CREATE decision', () => {
    const d = seedDecisions([
      makeMatch({
        saved_decision: {
          project_id: null,
          program_action: 'create',
          program_id: null,
          new_program_name: 'Marxan',
        },
      }),
    ]).s1;
    expect(d.program_action).toBe('create');
    expect(d.new_program_name).toBe('Marxan');
  });

  it('falls back to none when saved_decision is null', () => {
    const d = seedDecisions([makeMatch({ saved_decision: null })]).s1;
    expect(d.program_action).toBe('none');
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
