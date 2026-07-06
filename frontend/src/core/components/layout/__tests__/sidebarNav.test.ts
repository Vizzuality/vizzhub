import { describe, it, expect } from 'vitest';
import { activeSubItemTo } from '../sidebarNav';

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
