import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '@/core/services/client';
import { portfolioApi } from '../portfolio';

vi.mock('@/core/services/client');

describe('portfolioApi', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists clients with params', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 50 },
    });
    const res = await portfolioApi.listClients({ search: 'acme' });
    expect(api.get).toHaveBeenCalledWith('/clients', { params: { search: 'acme' } });
    expect(res.total).toBe(0);
  });

  it('merges clients', async () => {
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { merged_projects: 3, target: { id: 't' } },
    });
    const res = await portfolioApi.mergeClients('t', { source_ids: ['a', 'b'] });
    expect(api.post).toHaveBeenCalledWith('/clients/t/merge', { source_ids: ['a', 'b'] });
    expect(res.merged_projects).toBe(3);
  });

  it('fetches dashboard summary with a year param', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { year: 2026, available_years: [2026], kpis: {}, volume_by_year: [],
        spend_by_client: [], margin_split: {}, breakdowns: [] },
    });
    await portfolioApi.dashboard.summary(2026);
    expect(api.get).toHaveBeenCalledWith('/portfolio/dashboard/summary', { params: { year: 2026 } });
  });
});
