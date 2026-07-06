import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProgramDetail from '../ProgramDetail';

const mockUsePermission = vi.fn(() => true);
const DETAIL = {
  id: 'p1',
  name: 'Alpha Program',
  profile: {
    objective: 'The objective', short_description: 'Desc', web_copy: null,
    impact_story: null, main_partner: 'Partner X', stage: 'live', on_website: false,
  },
  terms: [
    { term_id: 't1', taxonomy_id: 'x1', taxonomy_slug: 'service', name: 'Tools', is_primary: false },
  ],
  clients: [{ id: 'c1', name: 'Acme' }],
  projects: [
    {
      id: 'pr1', name: 'Alpha 2024', status: 'live', start_year: 2024, end_year: 2025,
      has_scorecard: true, is_billable: true, is_absence: false,
      client_id: 'c1', client_name: 'Acme',
    },
    {
      id: 'pr2', name: 'Alpha internal', status: 'live', start_year: 2023, end_year: null,
      has_scorecard: false, is_billable: false, is_absence: false,
      client_id: null, client_name: null,
    },
  ],
};

vi.mock('../../hooks/usePrograms', () => ({
  useProgramDetail: () => ({ data: DETAIL, isLoading: false }),
  useUpdateProgramProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useReplaceProgramTerms: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRenameProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetProjectProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProgramOptions: () => ({ data: [] }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({ data: [], isLoading: false }),
}));
vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockUsePermission>) => mockUsePermission(...args),
}));

function renderPage(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/admin/portfolio/programs/p1']}>
        <Routes>
          <Route path="/admin/portfolio/programs/:programId" element={<ProgramDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProgramDetail', () => {
  it('renders name, narrative fields and tags', () => {
    renderPage();
    expect(screen.getByText('Alpha Program')).toBeInTheDocument();
    expect(screen.getByText('The objective')).toBeInTheDocument();
    expect(screen.getByText('Tools')).toBeInTheDocument();
  });

  it('shows Scorecard link only for has_scorecard and Tracker link only for billable', () => {
    renderPage();
    const scorecardLinks = screen.getAllByRole('link', { name: /scorecard/i });
    expect(scorecardLinks).toHaveLength(1);
    expect(scorecardLinks[0]).toHaveAttribute('href', '/scorecard/pr1');
    const trackerLinks = screen.getAllByRole('link', { name: /tracker/i });
    expect(trackerLinks).toHaveLength(1);
    expect(trackerLinks[0]).toHaveAttribute('href', '/tracker/projects/pr1');
  });

  it('hides edit affordances without manage permission', () => {
    mockUsePermission.mockReturnValue(false);
    renderPage();
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    mockUsePermission.mockReturnValue(true);
  });
});
