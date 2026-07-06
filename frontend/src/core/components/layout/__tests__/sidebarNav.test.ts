import { describe, it, expect } from 'vitest';
import { activeSubItemTo, projectsHubItems, PROJECTS_HUB_ITEMS } from '../sidebarNav';

const PORTFOLIO = [
  { to: '/admin/portfolio', label: 'Programs' },
  { to: '/admin/portfolio/clients', label: 'Clients' },
  { to: '/admin/portfolio/dashboard', label: 'Dashboard' },
] as const;

describe('activeSubItemTo', () => {
  it('activates the index route only on its exact path', () => {
    expect(activeSubItemTo('/admin/portfolio', PORTFOLIO)).toBe('/admin/portfolio');
  });

  it('activates the more specific sibling, not the index, on a child path', () => {
    // The Clients (index) tab must NOT win on the Dashboard page.
    expect(activeSubItemTo('/admin/portfolio/dashboard', PORTFOLIO)).toBe(
      '/admin/portfolio/dashboard',
    );
  });

  it('keeps the specific sibling active on deeper descendants', () => {
    expect(activeSubItemTo('/admin/portfolio/dashboard/2024', PORTFOLIO)).toBe(
      '/admin/portfolio/dashboard',
    );
  });

  it('returns null when nothing matches (mere string prefix is not a segment match)', () => {
    expect(activeSubItemTo('/admin/portfolio-archive', PORTFOLIO)).toBeNull();
  });
});

describe('projectsHubItems', () => {
  it('returns all four items when portfolio is visible', () => {
    expect(projectsHubItems(true).map((i) => i.label)).toEqual([
      'All Projects',
      'Scorecard',
      'Portfolio',
      'Global Scores',
    ]);
  });

  it('excludes Portfolio when not visible', () => {
    const items = projectsHubItems(false);
    expect(items.map((i) => i.label)).toEqual(['All Projects', 'Scorecard', 'Global Scores']);
  });
});

describe('activeSubItemTo over hub items', () => {
  it.each([
    ['/projects', '/projects'],
    ['/projects/abc-123/overview', '/projects'],
    ['/scorecard', '/scorecard'],
    ['/scorecard/global', '/scorecard/global'],
    ['/admin/portfolio', '/admin/portfolio'],
    ['/admin/portfolio/programs/xyz', '/admin/portfolio'],
  ])('%s resolves to %s', (path, expected) => {
    expect(activeSubItemTo(path, PROJECTS_HUB_ITEMS)).toBe(expected);
  });

  it('returns null on unrelated paths', () => {
    expect(activeSubItemTo('/capacity/insights', PROJECTS_HUB_ITEMS)).toBeNull();
  });
});
