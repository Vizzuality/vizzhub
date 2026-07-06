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

  it('shows All Projects as current page for /projects', () => {
    renderAt('/projects');
    expect(screen.getByText('All Projects')).toBeInTheDocument();
  });

  it('links Projects to /projects for /projects', () => {
    renderAt('/projects');
    const link = screen.getByRole('link', { name: 'Projects' });
    expect(link).toHaveAttribute('href', '/projects');
  });

  it('shows Projects › Scorecard for /scorecard', () => {
    renderAt('/scorecard');
    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects');
    expect(screen.getByText('Scorecard')).toBeInTheDocument();
  });

  it('shows Projects › Global Scores for /scorecard/global', () => {
    renderAt('/scorecard/global');
    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects');
    expect(screen.getByText('Global Scores')).toBeInTheDocument();
  });

  it('shows Projects › Portfolio › Programs for /admin/portfolio', () => {
    renderAt('/admin/portfolio');
    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects');
    expect(screen.getByRole('link', { name: 'Portfolio' })).toHaveAttribute('href', '/admin/portfolio');
    expect(screen.getByText('Programs')).toBeInTheDocument();
  });

  it('shows Projects › Portfolio › Clients for /admin/portfolio/clients', () => {
    renderAt('/admin/portfolio/clients');
    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects');
    expect(screen.getByRole('link', { name: 'Portfolio' })).toHaveAttribute('href', '/admin/portfolio');
    expect(screen.getByText('Clients')).toBeInTheDocument();
  });

  it('shows Projects › Portfolio › Dashboard for /admin/portfolio/dashboard', () => {
    renderAt('/admin/portfolio/dashboard');
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('shows Projects › Portfolio › Program for /admin/portfolio/programs/abc', () => {
    renderAt('/admin/portfolio/programs/abc');
    expect(screen.getByRole('link', { name: 'Projects' })).toHaveAttribute('href', '/projects');
    expect(screen.getByText('Program')).toBeInTheDocument();
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

  it('links Projects to /projects in legacy scorecard project detail', () => {
    renderAt('/scorecard/p1');
    const link = screen.getByRole('link', { name: 'Projects' });
    expect(link).toHaveAttribute('href', '/projects');
  });

  it('falls back to Dashboard for unrecognised paths', () => {
    renderAt('/some/unknown/path');
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
