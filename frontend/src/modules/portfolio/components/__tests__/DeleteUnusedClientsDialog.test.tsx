import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '@/test/setup';
import { DeleteUnusedClientsDialog } from '../DeleteUnusedClientsDialog';

const BASE = '/api';

function renderDialog(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <DeleteUnusedClientsDialog open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe('DeleteUnusedClientsDialog', () => {
  beforeEach(() => server.resetHandlers());

  it('lists the clients without projects and deletes them on confirm', async () => {
    let deleted = false;
    server.use(
      http.get(`${BASE}/clients/unused`, () =>
        HttpResponse.json([
          { id: 'a', name: 'Alpha Empty' },
          { id: 'z', name: 'Zeta Empty' },
        ]),
      ),
      http.delete(`${BASE}/clients/unused`, () => {
        deleted = true;
        return HttpResponse.json({ deleted: 2 });
      }),
    );
    renderDialog();

    expect(await screen.findByText('Alpha Empty')).toBeInTheDocument();
    expect(screen.getByText('Zeta Empty')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /delete 2 clients/i }));

    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText('Deleted 2 clients.')).toBeInTheDocument();
  });

  it('has nothing to delete when every client has projects', async () => {
    server.use(http.get(`${BASE}/clients/unused`, () => HttpResponse.json([])));
    renderDialog();

    expect(await screen.findByText(/every client has at least one project/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete 0 clients/i })).toBeDisabled();
  });
});
