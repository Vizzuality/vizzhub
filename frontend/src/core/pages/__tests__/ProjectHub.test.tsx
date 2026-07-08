import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProjectHubLayout from '../ProjectHub';

vi.mock('@/core/hooks/useProjects', () => ({
  useProject: () => ({ data: { id: 'p1', name: 'Ocean Watch', has_scorecard: true, status: 'live' }, isLoading: false }),
}));
vi.mock('@/core/permissions', () => ({
  usePermission: () => true,
  Action: { PROJECTS_MANAGE: 'projects:manage', SCORECARD_VIEW: 's', TRACKER_VIEW: 't', PORTFOLIO_VIEW: 'p' },
}));
vi.mock('@/modules/scorecard/hooks/useProjectScoresMap', () => ({
  useProjectScoresMap: () => ({ scoresMap: {} }),
}));
vi.mock('@/modules/tracker/public', () => ({
  useProjectCostsMap: () => ({ costsMap: {} }),
  useProjectProgressMap: () => ({ progressMap: {} }),
}));

describe('ProjectHubLayout', () => {
  it('renders header + tabs + the facet outlet', () => {
    render(
      <MemoryRouter initialEntries={['/projects/p1/tracker']}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectHubLayout />}>
            <Route path="tracker" element={<div>TRACKER PANEL</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Ocean Watch')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /tracker/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /overview/i })).toBeNull();
    expect(screen.getByText('TRACKER PANEL')).toBeInTheDocument();
  });
});
