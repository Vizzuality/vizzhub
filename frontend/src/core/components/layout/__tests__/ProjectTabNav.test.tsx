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

const project = { id: 'p1', name: 'X', has_scorecard: true } as Project;

describe('ProjectTabNav', () => {
  it('shows permitted tabs and a clean base-path href', () => {
    render(
      <MemoryRouter initialEntries={['/projects/p1/scorecard?date=2026-01']}>
        <ProjectProvider project={project}><ProjectTabNav /></ProjectProvider>
      </MemoryRouter>,
    );
    expect(screen.queryByRole('link', { name: /overview/i })).toBeNull(); // tab removed
    expect(screen.getByRole('link', { name: /scorecard/i })).toHaveAttribute('href', '/projects/p1/scorecard');
    expect(screen.queryByRole('link', { name: /tracker/i })).toBeNull(); // gated out
  });
});
