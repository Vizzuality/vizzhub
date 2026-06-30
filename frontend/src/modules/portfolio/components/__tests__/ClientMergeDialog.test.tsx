import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ClientMergeDialog } from '../ClientMergeDialog';

const mergeMutate = vi.fn().mockResolvedValue({ merged_projects: 2 });
vi.mock('../../hooks/useClients', () => ({
  useMergeClients: () => ({ mutateAsync: mergeMutate, isPending: false }),
}));

const candidates = [
  { id: 'a', name: 'Acme', slug: 'acme', is_active: true, project_count: 2, created_at: '', updated_at: '' },
  { id: 'b', name: 'Acme Inc', slug: 'acme-inc', is_active: true, project_count: 1, created_at: '', updated_at: '' },
];

describe('ClientMergeDialog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('merges sources into the chosen target', async () => {
    render(
      <ClientMergeDialog open onOpenChange={() => {}} candidates={candidates} onMerged={() => {}} />,
    );
    // First candidate is the default target → 'b' is the source
    fireEvent.click(screen.getByRole('button', { name: /merge/i }));
    await waitFor(() =>
      expect(mergeMutate).toHaveBeenCalledWith({ targetId: 'a', data: { source_ids: ['b'] } }),
    );
  });
});
