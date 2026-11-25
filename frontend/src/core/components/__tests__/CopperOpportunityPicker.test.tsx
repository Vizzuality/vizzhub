import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '@/test/setup';
import { CopperOpportunityPicker } from '../CopperOpportunityPicker';
import type { CopperOpportunity } from '@/core/types/copper';

const BASE = '/api';

function opp(overrides: Partial<CopperOpportunity>): CopperOpportunity {
  return {
    opportunity_id: 1,
    name: 'Opportunity',
    group: 'pending_signature',
    stage_changed_on: '2026-11-01',
    company_name: 'Acme',
    code: 'ACM.OPP.1',
    currency: 'dollar',
    original_budget: 1000,
    start_date: null,
    end_date: null,
    client_id: null,
    client_name: null,
    new_client: null,
    linked_projects: [],
    suggestion: null,
    ...overrides,
  };
}

function renderPicker(onImport = vi.fn()): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CopperOpportunityPicker onImport={onImport} />
    </QueryClientProvider>,
  );
}

describe('CopperOpportunityPicker', () => {
  beforeEach(() => server.resetHandlers());

  it('groups opportunities and blocks the ones already in VizzHub', async () => {
    server.use(
      http.get(`${BASE}/projects/copper-opportunities`, () =>
        HttpResponse.json([
          opp({
            opportunity_id: 1,
            name: 'Colorado Forest Atlas',
            linked_projects: [{ id: 'p1', name: 'Colorado Forest Atlas' }],
          }),
          opp({ opportunity_id: 2, name: 'Rangelands 2026 extension', group: 'signed' }),
        ]),
      ),
    );
    renderPicker();

    expect(await screen.findByText(/pending signature/i)).toBeInTheDocument();
    expect(screen.getByText(/signed, not in vizzhub/i)).toBeInTheDocument();
    expect(screen.getByText(/already in vizzhub: colorado forest atlas/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /import colorado forest atlas/i })).toBeNull();
    expect(screen.getByRole('button', { name: /import rangelands 2026 extension/i })).toBeEnabled();
  });

  it('passes the chosen opportunity to the form', async () => {
    const onImport = vi.fn();
    const wrip = opp({ opportunity_id: 3, name: 'WRIP Design' });
    server.use(http.get(`${BASE}/projects/copper-opportunities`, () => HttpResponse.json([wrip])));
    renderPicker(onImport);

    await userEvent.click(await screen.findByRole('button', { name: /import wrip design/i }));

    expect(onImport).toHaveBeenCalledWith(wrip);
  });

  it('links an opportunity to the suggested existing project', async () => {
    let patched: { id: string; body: unknown } | null = null;
    server.use(
      http.get(`${BASE}/projects/copper-opportunities`, () =>
        HttpResponse.json([
          opp({
            opportunity_id: 33647599,
            name: 'Global Mangrove Watch updates 2026',
            group: 'signed',
            suggestion: { id: 'gmw9', name: 'Global Mangrove Watch Phase 9' },
          }),
        ]),
      ),
      http.patch(`${BASE}/projects/:id`, async ({ params, request }) => {
        patched = { id: params.id as string, body: await request.json() };
        return HttpResponse.json({ id: params.id });
      }),
    );
    renderPicker();

    const row = (await screen.findByText('Global Mangrove Watch updates 2026')).closest('li');
    await userEvent.click(
      within(row as HTMLElement).getByRole('button', {
        name: /it is global mangrove watch phase 9/i,
      }),
    );

    await waitFor(() =>
      expect(patched).toEqual({ id: 'gmw9', body: { copper_opportunity_id: 33647599 } }),
    );
  });

  it('says so when linking to the suggested project fails', async () => {
    server.use(
      http.get(`${BASE}/projects/copper-opportunities`, () =>
        HttpResponse.json([
          opp({ name: 'GMW updates', suggestion: { id: 'gmw9', name: 'GMW Phase 9' } }),
        ]),
      ),
      http.patch(`${BASE}/projects/:id`, () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );
    renderPicker();

    await userEvent.click(await screen.findByRole('button', { name: /it is gmw phase 9/i }));

    expect(await screen.findByText(/could not link/i)).toBeInTheDocument();
  });
});
