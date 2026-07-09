import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import { ProjectTabNav } from '../ProjectTabNav';
import type { Project } from '@/core/types/project';

vi.mock('@/core/permissions', () => ({
  usePermission: (p: string) => p !== 'tracker:view', // tracker hidden
  Action: { SCORECARD_VIEW: 'scorecard:view', TRACKER_VIEW: 'tracker:view', PORTFOLIO_VIEW: 'portfolio:view' },
}));

const project = { id: 'p1', name: 'X', has_scorecard: true, program_id: 'prog-1' } as Project;

function renderNav(p: Project): void {
  render(
    <MemoryRouter initialEntries={['/projects/p1/scorecard?date=2026-01']}>
      <ProjectProvider project={p}><ProjectTabNav /></ProjectProvider>
    </MemoryRouter>,
  );
}

describe('ProjectTabNav', () => {
  it('shows permitted tabs and a clean base-path href', () => {
    renderNav(project);
    expect(screen.queryByRole('link', { name: /overview/i })).toBeNull(); // tab removed
    expect(screen.getByRole('link', { name: /scorecard/i })).toHaveAttribute('href', '/projects/p1/scorecard');
    expect(screen.getByRole('link', { name: /portfolio/i })).toHaveAttribute('href', '/projects/p1/portfolio');
    expect(screen.queryByRole('link', { name: /tracker/i })).toBeNull(); // gated out
  });

  it('hides the Portfolio tab when the project has no program', () => {
    renderNav({ ...project, program_id: null } as Project);
    expect(screen.queryByRole('link', { name: /portfolio/i })).toBeNull();
  });
});
