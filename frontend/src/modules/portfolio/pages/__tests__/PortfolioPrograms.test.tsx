import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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

const ORPHAN_PROJECT = {
  id: 'or1', name: 'Orphan', status: 'live', start_year: null, end_year: null,
  has_scorecard: false, is_billable: true, is_absence: false,
  client_id: null, client_name: null,
};

const mockUseProgramIndex = vi.fn(() => ({
  data: {
    programs: [PROGRAM],
    total: 1,
    pages: 1,
  },
  isLoading: false,
}));

vi.mock('../../hooks/usePrograms', () => ({
  useProgramIndex: (...args: Parameters<typeof mockUseProgramIndex>) => mockUseProgramIndex(...args),
  useUnassignedProjects: () => ({
    data: [ORPHAN_PROJECT],
    isLoading: false,
  }),
  useStageOptions: () => ({ data: ['live', 'pipeline'], isLoading: false }),
  useCreateProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetProjectProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProgramOptions: () => ({ data: [{ id: 'p1', name: 'Alpha Program' }] }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({
    data: [
      {
        id: 'tax-svc', slug: 'service', name: 'Service', description: null,
        cardinality: 'multi', allows_primary: true, is_active: true, sort_order: 0,
        terms: [
          { id: 't-tools', taxonomy_id: 'tax-svc', slug: 'tools', name: 'Tools', description: null, sort_order: 0, is_active: true },
        ],
      },
      {
        id: 'tax-geo', slug: 'geography', name: 'Geography', description: null,
        cardinality: 'multi', allows_primary: false, is_active: true, sort_order: 1,
        terms: [],
      },
    ],
    isLoading: false,
  }),
}));
vi.mock('../../hooks/useClientOptions', () => ({
  useClientOptions: () => ({ data: [{ id: 'c1', name: 'Acme', code: null }] }),
}));
vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockUsePermission>) => mockUsePermission(...args),
}));

function renderPage(options?: { initialEntries?: string[] }): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={options?.initialEntries ?? ['/portfolio']}>
        <Routes>
          <Route path="/portfolio" element={<PortfolioPrograms />} />
          <Route
            path="/portfolio/programs/:programId"
            element={<div>PROGRAM DETAIL</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioPrograms', () => {
  beforeEach(() => {
    mockUseProgramIndex.mockReturnValue({
      data: { programs: [PROGRAM], total: 1, pages: 1 },
      isLoading: false,
    });
    mockUsePermission.mockReturnValue(true);
  });

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
  });

  it('shows an enabled New program button and assign controls with manage permission', () => {
    mockUsePermission.mockReturnValue(true);
    renderPage();
    expect(screen.getByRole('button', { name: /new program/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /assign/i })).toBeInTheDocument();
  });

  it('renders one filter button per active taxonomy and a stage select', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /^service/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^geography/i })).toBeInTheDocument();
    expect(screen.getByText('All stages')).toBeInTheDocument();
  });

  it('defaults to newest-first sort with no website filter', () => {
    renderPage();
    expect(screen.getByText('In website: all')).toBeInTheDocument();
    expect(screen.getByText('Newest first')).toBeInTheDocument();
    expect(mockUseProgramIndex).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'recent', on_website: undefined }),
    );
  });

  it('passes website filter and sort from the URL to the index query', () => {
    renderPage({ initialEntries: ['/portfolio?website=yes&sort=alpha'] });
    expect(mockUseProgramIndex).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'alpha', on_website: true }),
    );
    expect(screen.getByText('In website: yes')).toBeInTheDocument();
    expect(screen.getByText('Alphabetical')).toBeInTheDocument();
  });

  it('maps website=no to on_website false', () => {
    renderPage({ initialEntries: ['/portfolio?website=no'] });
    expect(mockUseProgramIndex).toHaveBeenCalledWith(
      expect.objectContaining({ on_website: false }),
    );
  });

  it('shows pagination and navigates pages via URL state', () => {
    mockUseProgramIndex.mockReturnValue({
      data: { programs: [PROGRAM], total: 30, pages: 2 },
      isLoading: false,
    });
    renderPage();
    expect(screen.getByText(/showing \d+ of 30 programs/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument();
  });

  it('resets to page 1 when a filter changes', async () => {
    mockUseProgramIndex.mockReturnValue({
      data: { programs: [PROGRAM], total: 30, pages: 2 },
      isLoading: false,
    });
    renderPage({ initialEntries: ['/portfolio?page=2'] });
    expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument();
    vi.useFakeTimers();
    fireEvent.change(screen.getByPlaceholderText(/search text/i), {
      target: { value: 'mangrove' },
    });
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    vi.useRealTimers();
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
  });

  it('renders the unassigned tray from its own endpoint', () => {
    renderPage();
    expect(screen.getByText('Orphan')).toBeInTheDocument();
  });

  it('program combobox jumps straight to the program detail', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /go to program/i }));
    fireEvent.click(screen.getByRole('option', { name: /alpha program/i }));
    expect(screen.getByText('PROGRAM DETAIL')).toBeInTheDocument();
  });
});
