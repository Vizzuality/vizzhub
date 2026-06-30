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
});
