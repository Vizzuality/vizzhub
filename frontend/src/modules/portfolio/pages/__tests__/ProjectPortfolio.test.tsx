import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '@/core/contexts/ProjectContext';
import ProjectPortfolio from '../ProjectPortfolio';
import type { Project } from '@/core/types/project';

const PROGRAM = {
  id: 'prog-1',
  name: 'Mangrove Atlas',
  profile: {
    objective: 'Map mangroves', short_description: null, web_copy: null,
    website_url: null, impact_story: null, main_partner: null,
    stage: 'live', on_website: true,
  },
  terms: [
    { term_id: 't1', taxonomy_id: 'x1', taxonomy_slug: 'service', name: 'Tools', is_primary: false },
  ],
  clients: [],
  projects: [
    {
      id: 'pr1', name: 'GMW Phase 8', status: 'live', start_year: 2025, end_year: 2025,
      has_scorecard: false, is_billable: false, is_absence: false,
      client_id: null, client_name: null,
    },
  ],
};

vi.mock('../../hooks/usePrograms', () => ({
  useProgramDetail: (id: string | undefined) => ({
    data: id ? PROGRAM : undefined,
    isLoading: false,
  }),
  useUpdateProgramProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({ data: [], isLoading: false }),
}));

function renderFacet(programId: string | null): void {
  const project = { id: 'p1', name: 'GMW Phase 8', program_id: programId } as Project;
  render(
    <MemoryRouter>
      <ProjectProvider project={project}><ProjectPortfolio /></ProjectProvider>
    </MemoryRouter>,
  );
}

describe('ProjectPortfolio facet', () => {
  it('renders the full program view inline (no Open in Portfolio button)', () => {
    renderFacet('prog-1');
    expect(screen.getByText('Mangrove Atlas')).toBeInTheDocument();
    expect(screen.getByText('Map mangroves')).toBeInTheDocument();
    expect(screen.getByText('GMW Phase 8')).toBeInTheDocument(); // sibling iterations
    expect(screen.queryByRole('link', { name: /open in portfolio/i })).not.toBeInTheDocument();
  });

  it('is read-only without manage permission', () => {
    renderFacet('prog-1');
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
  });

  it('shows an empty state when the project has no program', () => {
    renderFacet(null);
    expect(screen.getByText(/not assigned to any program/i)).toBeInTheDocument();
  });
});
