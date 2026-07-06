export interface SubItem {
  readonly to: string;
  readonly label: string;
}

/**
 * The active sub-item is the one whose `to` is the longest prefix of the current path
 * (exact or a segment-boundary descendant). Longest-prefix-wins stops an index route
 * (`/admin/portfolio`) from lighting up on a sibling's page (`/admin/portfolio/dashboard`),
 * where a plain prefix test would match both. Returns the winning `to`, or null.
 */
export function activeSubItemTo(pathname: string, items: readonly SubItem[]): string | null {
  let best: string | null = null;
  for (const { to } of items) {
    const matches = pathname === to || pathname.startsWith(`${to}/`);
    if (matches && (best === null || to.length > best.length)) {
      best = to;
    }
  }
  return best;
}
