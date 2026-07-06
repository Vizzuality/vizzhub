import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import PortfolioPrograms from '../PortfolioPrograms';

const mockUsePermission = vi.fn(() => true);

const PROGRAM = {
  id: 'p1',
  name: 'Alpha Program',
  profile: {
    objective: null, short_description: 'Short desc', web_copy: null,
    impact_story: null, main_partner: null, stage: 'live', on_website: true,
  },
  terms: [
    { term_id: 't1', taxonomy_id: 'x1', taxonomy_slug: 'service', name: 'Tools', is_primary: false },
    { term_id: 't2', taxonomy_id: 'x2', taxonomy_slug: 'topics', name: 'Biodiversity', is_primary: false },
  ],
  clients: [{ id: 'c1', name: 'Acme' }],
  projects: [
    {
      id: 'pr1', name: 'Alpha 2024', status: 'live', start_year: 2024, end_year: 2025,
      has_scorecard: true, is_billable: true, is_absence: false,
      client_id: 'c1', client_name: 'Acme',
    },
  ],
};

vi.mock('../../hooks/usePrograms', () => ({
  useProgramIndex: () => ({
    data: {
      programs: [PROGRAM],
      unassigned_projects: [
        {
          id: 'or1', name: 'Orphan', status: 'live', start_year: null, end_year: null,
          has_scorecard: false, is_billable: true, is_absence: false,
          client_id: null, client_name: null,
        },
      ],
    },
    isLoading: false,
  }),
  useCreateProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetProjectProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProgramOptions: () => ({ data: [{ id: 'p1', name: 'Alpha Program' }] }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({ data: [], isLoading: false }),
}));
vi.mock('../../hooks/useClientOptions', () => ({
  useClientOptions: () => ({ data: [{ id: 'c1', name: 'Acme', code: null }] }),
}));
vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockUsePermission>) => mockUsePermission(...args),
}));

function renderPage(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <PortfolioPrograms />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioPrograms', () => {
  it('renders program cards with tags from all taxonomies and iteration summary', () => {
    renderPage();
    expect(screen.getByText('Alpha Program')).toBeInTheDocument();
    expect(screen.getByText('Tools')).toBeInTheDocument();
    expect(screen.getByText('Biodiversity')).toBeInTheDocument(); // topics chip visible
    expect(screen.getByText(/1 active · 0 finished/)).toBeInTheDocument();
  });

  it('renders the unassigned tray last with its projects', () => {
    renderPage();
    expect(screen.getByText('No program')).toBeInTheDocument();
    expect(screen.getByText('Orphan')).toBeInTheDocument();
  });

  it('hides reorg affordances without manage permission', () => {
    mockUsePermission.mockReturnValue(false);
    renderPage();
    expect(screen.queryByRole('button', { name: /new program/i })).not.toBeInTheDocument();
    mockUsePermission.mockReturnValue(true);
  });

  it('shows an enabled New program button and assign controls with manage permission', () => {
    mockUsePermission.mockReturnValue(true);
    renderPage();
    expect(screen.getByRole('button', { name: /new program/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /assign/i })).toBeInTheDocument();
  });
});
