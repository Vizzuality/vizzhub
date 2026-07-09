import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgramTagsSection } from '../ProgramTagsSection';

vi.mock('../../hooks/useTaxonomies', () => ({
  useTaxonomies: () => ({
    data: [
      {
        id: 'tax-single', slug: 'client-type', name: 'Client Type', description: null,
        cardinality: 'single', allows_primary: false, is_active: true, sort_order: 0,
        terms: [
          { id: 'ngo', taxonomy_id: 'tax-single', slug: 'ngo', name: 'NGO', description: null, sort_order: 0, is_active: true },
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

const PROGRAM = {
  id: 'p1', name: 'Alpha', profile: null, clients: [], projects: [],
  terms: [
    { term_id: 'ngo', taxonomy_id: 'tax-single', taxonomy_slug: 'client-type', name: 'NGO', is_primary: false },
  ],
};

describe('ProgramTagsSection', () => {
  it('renders assigned chips grouped by taxonomy and a dash for empty ones', () => {
    render(<ProgramTagsSection program={PROGRAM} />);
    expect(screen.getByText('Client Type')).toBeInTheDocument();
    expect(screen.getByText('NGO')).toBeInTheDocument();
    expect(screen.getByText('Geography')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('is read-only: no edit buttons', () => {
    render(<ProgramTagsSection program={PROGRAM} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
