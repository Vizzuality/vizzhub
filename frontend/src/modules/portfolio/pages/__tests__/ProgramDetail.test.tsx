import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProgramDetail from '../ProgramDetail';

const mockUsePermission = vi.fn(() => true);
const mockDeleteProgram = vi.fn();
const DETAIL = {
  id: 'p1',
  name: 'Alpha Program',
  stage: 'Active',
  profile: {
    objective: 'The objective', short_description: 'Desc', web_copy: null,
    website_url: 'https://alpha.example.org', impact_story: null,
    main_partner: 'Partner X', stage: 'live', on_website: false,
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

const mockUseProgramDetail = vi.fn((): { data: unknown; isLoading: boolean } => ({
  data: DETAIL,
  isLoading: false,
}));

vi.mock('../../hooks/usePrograms', () => ({
  useProgramDetail: () => mockUseProgramDetail(),
  useDeleteProgram: () => ({ mutateAsync: mockDeleteProgram, isPending: false }),
  useUpdateProgramProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useReplaceProgramTerms: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRenameProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetProjectProgram: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useProgramOptions: () => ({ data: [] }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({
    data: [
      {
        id: 'x1', slug: 'service', name: 'Service', description: null,
        cardinality: 'multi', allows_primary: false, is_active: true, sort_order: 0,
        terms: [
          { id: 't1', taxonomy_id: 'x1', slug: 'tools', name: 'Tools', description: null, sort_order: 0, is_active: true },
        ],
      },
    ],
    isLoading: false,
  }),
}));
vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockUsePermission>) => mockUsePermission(...args),
}));

function renderPage(): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/portfolio/programs/p1']}>
        <Routes>
          <Route path="/portfolio/programs/:programId" element={<ProgramDetail />} />
          <Route path="/portfolio" element={<div>PROGRAM INDEX</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProgramDetail', () => {
  it('shows the stage derived from projects, not the stored profile value', () => {
    renderPage();
    expect(screen.getByText('Active · Acme')).toBeInTheDocument();
  });

  it('renders name, narrative fields, website link and tags', () => {
    renderPage();
    expect(screen.getByText('Alpha Program')).toBeInTheDocument();
    expect(screen.getByText('The objective')).toBeInTheDocument();
    expect(screen.getByText('Tools')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /alpha\.example\.org/i })).toHaveAttribute(
      'href',
      'https://alpha.example.org',
    );
  });

  it('opens the single edit form on Edit', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /edit portfolio content/i }));
    expect(screen.getByLabelText('Name')).toHaveValue('Alpha Program');
    expect(screen.getByLabelText('Website')).toHaveValue('https://alpha.example.org');
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
    expect(screen.queryByRole('button', { name: /actions for/i })).not.toBeInTheDocument();
    mockUsePermission.mockReturnValue(true);
  });

  it('shows one actions menu per iteration with manage permission (no inline selector)', () => {
    mockUsePermission.mockReturnValue(true);
    renderPage();
    expect(screen.getAllByRole('button', { name: /actions for/i })).toHaveLength(2);
    // The always-visible move combobox is gone.
    expect(screen.queryByRole('button', { name: /^move/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument();
  });

  it('disables delete while the program has projects attached', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /delete program/i })).toBeDisabled();
  });

  it('deletes an empty program after confirming in the overlay', async () => {
    mockUseProgramDetail.mockReturnValue({ data: { ...DETAIL, projects: [] }, isLoading: false });
    mockDeleteProgram.mockResolvedValue(undefined);
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /delete program/i }));
    expect(mockDeleteProgram).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog')).toHaveTextContent('Alpha Program');

    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(mockDeleteProgram).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('PROGRAM INDEX')).toBeInTheDocument();
    mockUseProgramDetail.mockReturnValue({ data: DETAIL, isLoading: false });
  });

  it('keeps the overlay open and shows the error when deletion is rejected', async () => {
    mockUseProgramDetail.mockReturnValue({ data: { ...DETAIL, projects: [] }, isLoading: false });
    mockDeleteProgram.mockRejectedValue(
      Object.assign(new Error('conflict'), {
        response: { status: 409, data: { detail: 'Program has projects attached' } },
      }),
    );
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /delete program/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    expect(await screen.findByText('Program has projects attached')).toBeInTheDocument();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    mockUseProgramDetail.mockReturnValue({ data: DETAIL, isLoading: false });
  });

  it('hides delete without manage permission', () => {
    mockUsePermission.mockReturnValue(false);
    renderPage();
    expect(screen.queryByRole('button', { name: /delete program/i })).not.toBeInTheDocument();
    mockUsePermission.mockReturnValue(true);
  });
});
