import type { ProjectIteration } from '../types/portfolio';

/** Outline-badge tints per taxonomy slug (literal Tailwind classes — no var() opacity). */
export const TAXONOMY_CHIP_CLASSES: Record<string, string> = {
  'impact-area': 'border-emerald-400/60 text-emerald-700 dark:text-emerald-300',
  service: 'border-sky-400/60 text-sky-700 dark:text-sky-300',
  'client-type': 'border-amber-400/60 text-amber-700 dark:text-amber-300',
  geography: 'border-violet-400/60 text-violet-700 dark:text-violet-300',
  topics: 'border-rose-400/60 text-rose-700 dark:text-rose-300',
};

export const TAXONOMY_CHIP_FALLBACK = 'border-border text-muted-foreground';

export function iterationSummary(projects: ProjectIteration[]): string {
  const finished = projects.filter((p) => p.status === 'finished').length;
  const active = projects.length - finished;
  const years = projects
    .flatMap((p) => [p.start_year, p.end_year])
    .filter((y): y is number => y != null);
  const counts = `${active} active · ${finished} finished`;
  if (years.length === 0) return counts;
  return `${counts} · ${Math.min(...years)}–${Math.max(...years)}`;
}
