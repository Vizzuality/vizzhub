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

describe('ProjectHubLayout', () => {
  it('renders header + tabs + the facet outlet', () => {
    render(
      <MemoryRouter initialEntries={['/projects/p1/overview']}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectHubLayout />}>
            <Route path="overview" element={<div>OVERVIEW PANEL</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Ocean Watch')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByText('OVERVIEW PANEL')).toBeInTheDocument();
  });
});
