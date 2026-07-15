export interface SubItem {
  readonly to: string;
  readonly label: string;
}

/**
 * The active sub-item is the one whose `to` is the longest prefix of the current path
 * (exact or a segment-boundary descendant). Longest-prefix-wins stops an index route
 * (`/portfolio`) from lighting up on a lookalike prefix (`/portfolio-archive`),
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

/**
 * Route prefix → section title shown in the app header. Longest prefix wins,
 * so `/tracker/my-report` beats `/tracker` and `/admin/iso` beats `/iso`.
 */
const SECTION_TITLES: readonly SubItem[] = [
  { to: '/projects', label: 'Tracker' },
  { to: '/scorecard', label: 'Scorecard' },
  { to: '/scorecard/global', label: 'Global Scores' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/tracker', label: 'Tracker' },
  { to: '/tracker/my-report', label: 'My Report' },
  { to: '/tracker/my-reports', label: 'My Report' },
  { to: '/tracker/how-to-report', label: 'My Report' },
  { to: '/capacity', label: 'Capacity' },
  { to: '/playbook', label: 'Playbook' },
  { to: '/events', label: 'Events' },
  { to: '/devstack', label: 'DevStack' },
  { to: '/iso', label: 'ISO' },
  { to: '/admin/scorecard-parameters', label: 'Parameters' },
  { to: '/admin/integrations', label: 'Integrations' },
  { to: '/admin/assets', label: 'Assets' },
  { to: '/admin/jobs', label: 'Jobs' },
  { to: '/admin/commands', label: 'Command Queue' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/notifications', label: 'Notifications' },
  { to: '/admin/tracker', label: 'Tracker' },
  { to: '/admin/portfolio', label: 'Portfolio' },
  { to: '/admin/iso', label: 'ISO' },
  { to: '/admin/accrual', label: 'Accrual' },
];

/** Project detail tabs carry the facet in a dynamic segment, out of reach of static prefixes. */
const PROJECT_DETAIL_TAB_RE = /^\/projects\/[^/]+\/(tracker|scorecard|portfolio)(?:\/|$)/;

const PROJECT_DETAIL_TAB_TITLES: Record<string, string> = {
  tracker: 'Tracker',
  scorecard: 'Scorecard',
  portfolio: 'Portfolio',
};

/** Section title for the app header, or null when no section matches (e.g. landing). */
export function sectionTitle(pathname: string): string | null {
  const detailTab = PROJECT_DETAIL_TAB_RE.exec(pathname);
  if (detailTab) return PROJECT_DETAIL_TAB_TITLES[detailTab[1]];
  const to = activeSubItemTo(pathname, SECTION_TITLES);
  if (to === null) return null;
  return SECTION_TITLES.find((item) => item.to === to)?.label ?? null;
}

export const PROJECTS_HUB_ITEMS: readonly SubItem[] = [
  { to: '/projects', label: 'Tracker' },
  { to: '/scorecard', label: 'Scorecard' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/scorecard/global', label: 'Global Scores' },
];

/** Portfolio is permission-gated; sidebar and hub tab bar share this filter. */
export function projectsHubItems(showPortfolio: boolean): readonly SubItem[] {
  return showPortfolio
    ? PROJECTS_HUB_ITEMS
    : PROJECTS_HUB_ITEMS.filter((item) => item.to !== '/portfolio');
}
