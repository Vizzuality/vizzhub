import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import ProjectOverview from '../ProjectOverview';
import type { Project } from '@/core/types/project';

vi.mock('@/core/permissions', () => ({
  usePermission: () => true,
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Action: { TRACKER_VIEW: 'tracker:view' },
}));
vi.mock('@/modules/scorecard/hooks/useProjectScoresMap', () => ({
  useProjectScoresMap: () => ({ scoresMap: { p1: 82 }, isLoading: false }),
}));
vi.mock('@/modules/tracker/public', () => ({
  useProjectCostsMap: () => ({ costsMap: { p1: { burn_percentage: 64 } }, isLoading: false }),
  useProjectProgressMap: () => ({ progressMap: {}, isLoading: false }),
}));

const project = { id: 'p1', name: 'Ocean Watch', has_scorecard: true, status: 'live' } as Project;

describe('ProjectOverview', () => {
  it('summarises score and burn', () => {
    render(
      <MemoryRouter>
        <ProjectProvider project={project}><ProjectOverview /></ProjectProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/82/)).toBeInTheDocument();
    expect(screen.getByText(/64/)).toBeInTheDocument();
  });
});
