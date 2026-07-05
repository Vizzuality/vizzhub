import type { OverviewDecision, OverviewMatch } from '../types/portfolio';

export type DecisionMap = Record<string, OverviewDecision>;

/**
 * Seed the editable decision map from each row's persisted `saved_decision` (the backend seeds a
 * program-first default at upload, so it is normally present). Falls back to a `none` decision.
 */
export function seedDecisions(matches: OverviewMatch[]): DecisionMap {
  const map: DecisionMap = {};
  for (const m of matches) {
    const s = m.saved_decision;
    map[m.staging_id] = {
      staging_id: m.staging_id,
      project_id: s?.project_id ?? null,
      program_action: s?.program_action ?? 'none',
      program_id: s?.program_id ?? null,
      new_program_name: s?.new_program_name ?? null,
    };
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
