import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ClientFormDialog } from '../ClientFormDialog';

const createMutate = vi.fn().mockResolvedValue({});
vi.mock('../../hooks/useClients', () => ({
  useCreateClient: () => ({ mutateAsync: createMutate, isPending: false }),
  useUpdateClient: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe('ClientFormDialog', () => {
  it('creates a client on save', async () => {
    render(<ClientFormDialog open onOpenChange={() => {}} client={null} />);
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'New Org' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(createMutate).toHaveBeenCalledWith({ name: 'New Org' }));
  });

  it('includes code and primary contact when provided', async () => {
    render(<ClientFormDialog open onOpenChange={() => {}} client={null} />);
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'New Org' } });
    fireEvent.change(screen.getByLabelText(/code/i), { target: { value: 'NEW' } });
    fireEvent.change(screen.getByLabelText(/primary contact/i), { target: { value: 'Jane Doe' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() =>
      expect(createMutate).toHaveBeenCalledWith({
        name: 'New Org',
        code: 'NEW',
        primary_contact: 'Jane Doe',
      }),
    );
  });
});
