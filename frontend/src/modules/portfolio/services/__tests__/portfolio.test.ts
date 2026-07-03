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

  it('dashboard.projects GETs /portfolio/dashboard/projects with year', async () => {
    const mockGet = api.get as ReturnType<typeof vi.fn>;
    mockGet.mockResolvedValueOnce({ data: { available_years: [2024], rows: [] } });
    await portfolioApi.dashboard.projects(2024);
    expect(mockGet).toHaveBeenCalledWith('/portfolio/dashboard/projects', { params: { year: 2024 } });
  });

  it('dashboard.clients GETs /portfolio/dashboard/clients without year', async () => {
    const mockGet = api.get as ReturnType<typeof vi.fn>;
    mockGet.mockResolvedValueOnce({ data: { available_years: [], rows: [] } });
    await portfolioApi.dashboard.clients();
    expect(mockGet).toHaveBeenCalledWith('/portfolio/dashboard/clients', { params: {} });
  });

  it('listClientOptions GETs /clients/options and returns the array', async () => {
    const mockGet = api.get as ReturnType<typeof vi.fn>;
    const data = [{ id: 'c1', name: 'Acme', code: 'ACME' }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await portfolioApi.listClientOptions();
    expect(mockGet).toHaveBeenCalledWith('/clients/options');
    expect(result).toEqual(data);
  });
});

describe('portfolioApi.import', () => {
  beforeEach(() => vi.clearAllMocks());

  it('uploads with multipart headers override', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { batch_id: 'b1', row_count: 3, old_count: 1 } });
    const file = new File(['x'], 'overview.xlsx');
    const result = await portfolioApi.import.upload(file);
    expect(result.batch_id).toBe('b1');
    const [, , config] = vi.mocked(api.post).mock.calls[0];
    expect((config as { headers: Record<string, unknown> }).headers['Content-Type']).toBeUndefined();
  });

  it('applies decisions', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { applied: 1, programs_created: 1, projects_linked_to_program: 1, skipped: 0, unmapped_terms: [], unresolved_clients: [] } });
    const result = await portfolioApi.import.apply('b1', [
      { staging_id: 's1', project_id: 'p1', program_action: 'create' },
    ]);
    expect(result.programs_created).toBe(1);
    expect(api.post).toHaveBeenCalledWith('/portfolio/import/b1/apply', [
      { staging_id: 's1', project_id: 'p1', program_action: 'create' },
    ]);
  });
});
