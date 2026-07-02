import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PageBreadcrumb } from '../PageBreadcrumb';

vi.mock('@/core/hooks/useProjects', () => ({
  useProject: (id: string) => ({
    data: id ? { id, name: 'Ocean Watch' } : undefined,
  }),
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={<PageBreadcrumb />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PageBreadcrumb', () => {
  it('renders Projects crumb for /projects', () => {
    renderAt('/projects');
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('renders project-aware crumbs for /projects/:id/:facet', () => {
    renderAt('/projects/p1/tracker');
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('Ocean Watch')).toBeInTheDocument();
    expect(screen.getByText('Tracker')).toBeInTheDocument();
  });

  it('links Projects to /projects in hub facet crumbs', () => {
    renderAt('/projects/p1/overview');
    const link = screen.getByRole('link', { name: 'Projects' });
    expect(link).toHaveAttribute('href', '/projects');
  });

  it('links project name to /projects/:id/overview', () => {
    renderAt('/projects/p1/scorecard');
    const link = screen.getByRole('link', { name: 'Ocean Watch' });
    expect(link).toHaveAttribute('href', '/projects/p1/overview');
  });

  it('shows Scorecard label for scorecard facet', () => {
    renderAt('/projects/p1/scorecard');
    expect(screen.getByText('Scorecard')).toBeInTheDocument();
  });

  it('shows Overview label for overview facet', () => {
    renderAt('/projects/p1/overview');
    expect(screen.getByText('Overview')).toBeInTheDocument();
  });

  it('shows raw facet segment when unlisted', () => {
    renderAt('/projects/p1/unknown-facet');
    expect(screen.getByText('unknown-facet')).toBeInTheDocument();
  });

  it('falls back to Dashboard for unrecognised paths', () => {
    renderAt('/some/unknown/path');
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
