import type { OverviewDecision, OverviewMatch } from '../types/portfolio';

export type DecisionMap = Record<string, OverviewDecision>;

/**
 * Program-first default: the Overview sheet is a catalogue of programs/products, so every
 * row anchors on a PROGRAM by default — profile + tags live on the program. Link the fuzzy
 * program match if any, else create a program from the row name. The reviewer switches a row
 * to project-anchor via the picker for the tail of one-off projects.
 */
export function seedDecisions(matches: OverviewMatch[]): DecisionMap {
  const map: DecisionMap = {};
  for (const m of matches) {
    if (m.suggested_program.program_id) {
      map[m.staging_id] = {
        staging_id: m.staging_id,
        project_id: null,
        program_action: 'link',
        program_id: m.suggested_program.program_id,
      };
    } else {
      map[m.staging_id] = {
        staging_id: m.staging_id,
        project_id: null,
        program_action: 'create',
        new_program_name: m.name,
      };
    }
  }
  return map;
}

/** Programs the fuzzy candidates surfaced first, then the full list, deduped by id. */
export function mergePrograms(
  candidates: readonly { id: string; name: string }[],
  all: readonly { id: string; name: string }[],
): { id: string; name: string }[] {
  const seen = new Set(candidates.map((c) => c.id));
  return [
    ...candidates.map((c) => ({ id: c.id, name: c.name })),
    ...all.filter((p) => !seen.has(p.id)),
  ];
}
