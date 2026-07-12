import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaxonomyFilter } from '../TaxonomyFilter';

const TAXONOMY = {
  id: 'tax-svc', slug: 'service', name: 'Service', description: null,
  cardinality: 'multi', allows_primary: true, is_active: true, sort_order: 0,
  terms: [
    { id: 'tools', taxonomy_id: 'tax-svc', slug: 'tools', name: 'Tools', description: null, sort_order: 0, is_active: true },
    { id: 'sci', taxonomy_id: 'tax-svc', slug: 'sci', name: 'Scientific', description: null, sort_order: 1, is_active: true },
    { id: 'old', taxonomy_id: 'tax-svc', slug: 'old', name: 'Retired', description: null, sort_order: 2, is_active: false },
  ],
};

describe('TaxonomyFilter', () => {
  it('shows the taxonomy name with a count of selected terms', () => {
    render(<TaxonomyFilter taxonomy={TAXONOMY} selectedIds={['tools']} onToggle={vi.fn()} />);
    expect(screen.getByRole('button', { name: /service \(1\)/i })).toBeInTheDocument();
  });

  it('lists only active terms and toggles on click', () => {
    const onToggle = vi.fn();
    render(<TaxonomyFilter taxonomy={TAXONOMY} selectedIds={[]} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button', { name: /service/i }));
    expect(screen.queryByLabelText('Retired')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Tools'));
    expect(onToggle).toHaveBeenCalledWith('tools');
  });
});
