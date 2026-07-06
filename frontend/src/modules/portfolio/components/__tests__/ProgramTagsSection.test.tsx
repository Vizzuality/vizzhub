import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProgramTagsSection } from '../ProgramTagsSection';

const replaceTerms = vi.fn().mockResolvedValue([]);

vi.mock('../../hooks/usePrograms', () => ({
  useReplaceProgramTerms: () => ({ mutateAsync: replaceTerms, isPending: false }),
}));
vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({
    data: [
      {
        id: 'tax-single', slug: 'client-type', name: 'Client Type', description: null,
        cardinality: 'single', allows_primary: false, is_active: true, sort_order: 0,
        terms: [
          { id: 'ngo', taxonomy_id: 'tax-single', slug: 'ngo', name: 'NGO', description: null, sort_order: 0, is_active: true },
          { id: 'gov', taxonomy_id: 'tax-single', slug: 'government', name: 'Government', description: null, sort_order: 1, is_active: true },
        ],
      },
    ],
    isLoading: false,
  }),
}));

const PROGRAM = {
  id: 'p1', name: 'Alpha', profile: null, clients: [], projects: [],
  terms: [
    { term_id: 'ngo', taxonomy_id: 'tax-single', taxonomy_slug: 'client-type', name: 'NGO', is_primary: false },
  ],
};

function renderSection(canManage = true): void {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ProgramTagsSection program={PROGRAM} canManage={canManage} />
    </QueryClientProvider>,
  );
}

describe('ProgramTagsSection', () => {
  beforeEach(() => replaceTerms.mockClear());

  it('renders assigned chips grouped by taxonomy', () => {
    renderSection();
    expect(screen.getByText('Client Type')).toBeInTheDocument();
    expect(screen.getByText('NGO')).toBeInTheDocument();
  });

  it('single cardinality: picking a second term replaces the first', async () => {
    renderSection();
    fireEvent.click(screen.getByRole('button', { name: /edit client type/i }));
    fireEvent.click(screen.getByLabelText('Government'));
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));
    await waitFor(() =>
      expect(replaceTerms).toHaveBeenCalledWith({
        taxonomy_id: 'tax-single',
        term_ids: ['gov'],
        primary_term_id: null,
      }),
    );
  });

  it('hides edit buttons without manage permission', () => {
    renderSection(false);
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
  });
});
