import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RsvpChips } from '../RsvpChips';

const setRsvpMock = vi.fn().mockResolvedValue(undefined);
const deleteRsvpMock = vi.fn().mockResolvedValue(undefined);

vi.mock('../../services/rsvps', () => ({
  rsvpsApi: {
    set: (...args: unknown[]) => setRsvpMock(...args),
    remove: (...args: unknown[]) => deleteRsvpMock(...args),
  },
}));

function render_(props: Parameters<typeof RsvpChips>[0]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RsvpChips {...props} />
    </QueryClientProvider>,
  );
}

describe('RsvpChips', () => {
  const counts = { going: 2, maybe: 1, not_going: 0 };

  it('clicking a chip that is not mine calls setRsvp', async () => {
    render_({ eventId: 'e1', counts, myStatus: null });
    fireEvent.click(screen.getByRole('button', { name: 'Going (2)' }));
    await waitFor(() => expect(setRsvpMock).toHaveBeenCalledWith('e1', 'going'));
  });

  it('clicking my current chip calls deleteRsvp', async () => {
    render_({ eventId: 'e1', counts, myStatus: 'going' });
    fireEvent.click(screen.getByRole('button', { name: 'Going (2)' }));
    await waitFor(() => expect(deleteRsvpMock).toHaveBeenCalledWith('e1'));
  });
});
