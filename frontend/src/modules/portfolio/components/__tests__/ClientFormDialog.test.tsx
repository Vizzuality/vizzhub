import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '@/test/setup';
import { ClientFormDialog } from '../ClientFormDialog';
import type { Client } from '../../types/portfolio';

const BASE = '/api';

const WWFINT: Client = {
  id: 'c-wwfint',
  name: 'Wwfint',
  slug: 'wwfint',
  code: null,
  primary_contact: null,
  copper_company_id: null,
  is_active: true,
  project_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const COMPANIES = [
  { id: 39906146, name: 'WWF', email_domain: 'wwfint.org', linked_client_name: null },
  { id: 65673505, name: 'WWF-Canada', email_domain: 'wwf.ca', linked_client_name: 'WWF-Canada' },
];

function renderDialog(client: Client | null): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ClientFormDialog open onOpenChange={() => {}} client={client} />
    </QueryClientProvider>,
  );
}

describe('ClientFormDialog', () => {
  beforeEach(() => server.resetHandlers());

  it('creates a client with the optional fields that were filled', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${BASE}/clients`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json({ ...WWFINT, id: 'new' }, { status: 201 });
      }),
    );
    renderDialog(null);

    await userEvent.type(screen.getByLabelText(/^name$/i), 'New Org');
    await userEvent.type(screen.getByLabelText(/^code$/i), 'NEW');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(posted).toEqual({ name: 'New Org', code: 'NEW' }));
    expect(screen.queryByLabelText(/copper company/i)).not.toBeInTheDocument();
  });

  it('links a client to the Copper company picked by hand', async () => {
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/clients/copper-companies`, () => HttpResponse.json(COMPANIES)),
      http.patch(`${BASE}/clients/:id`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(WWFINT);
      }),
    );
    renderDialog(WWFINT);

    const trigger = await screen.findByRole('combobox', { name: /copper company/i });
    await waitFor(() => expect(trigger).toBeEnabled());
    await userEvent.click(trigger);
    expect(screen.getByRole('option', { name: /wwf-canada/i })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    await userEvent.click(screen.getByRole('option', { name: /^wwf \(wwfint\.org\)/i }));
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(patched?.copper_company_id).toBe(39906146));
  });

  it('leaves the Copper link out of the update when it did not change', async () => {
    let patched: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/clients/copper-companies`, () => HttpResponse.json(COMPANIES)),
      http.patch(`${BASE}/clients/:id`, async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(WWFINT);
      }),
    );
    renderDialog(WWFINT);

    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched).not.toHaveProperty('copper_company_id');
  });

  it('hides the Copper field when Copper is not connected', async () => {
    let asked = false;
    server.use(
      http.get(`${BASE}/clients/copper-companies`, () => {
        asked = true;
        return HttpResponse.json({ detail: 'Copper is not connected' }, { status: 409 });
      }),
    );
    renderDialog(WWFINT);

    await waitFor(() => expect(asked).toBe(true));
    await waitFor(() =>
      expect(screen.queryByRole('combobox', { name: /copper company/i })).not.toBeInTheDocument(),
    );
  });

  it('shows why the save was rejected and keeps the dialog open', async () => {
    server.use(
      http.get(`${BASE}/clients/copper-companies`, () => HttpResponse.json(COMPANIES)),
      http.patch(`${BASE}/clients/:id`, () =>
        HttpResponse.json(
          { detail: 'This Copper company is already linked to another client' },
          { status: 409 },
        ),
      ),
    );
    renderDialog(WWFINT);

    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(await screen.findByText(/already linked to another client/i)).toBeInTheDocument();
  });
});
