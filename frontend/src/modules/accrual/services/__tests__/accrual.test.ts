import { describe, it, expect, vi, beforeEach } from 'vitest';
import { accrualApi } from '@/modules/accrual/services/accrual';
import api from '@/core/services/client';

vi.mock('@/core/services/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

describe('accrualApi.periods', () => {
  it('list calls GET /api/accrual/periods', async () => {
    (api.get as any).mockResolvedValue({ data: [] });
    await accrualApi.periods.list();
    expect(api.get).toHaveBeenCalledWith('/accrual/periods');
  });

  it('current calls GET /api/accrual/periods/current', async () => {
    (api.get as any).mockResolvedValue({ data: null });
    await accrualApi.periods.current();
    expect(api.get).toHaveBeenCalledWith('/accrual/periods/current');
  });

  it('create POSTs the payload', async () => {
    (api.post as any).mockResolvedValue({ data: { id: 'p1' } });
    await accrualApi.periods.create({ start_date: '2026-01-01' });
    expect(api.post).toHaveBeenCalledWith('/accrual/periods', {
      start_date: '2026-01-01',
    });
  });
});

describe('accrualApi.cells.grid', () => {
  it('GETs /accrual/grid with filter params', async () => {
    (api.get as any).mockResolvedValue({ data: { projects: [], cells: [], months: [] } });
    await accrualApi.cells.grid({ year_from: 2026, year_to: 2026, status: 'live' });
    expect(api.get).toHaveBeenCalledWith('/accrual/grid', {
      params: { year_from: 2026, year_to: 2026, status: 'live' },
    });
  });

  it('omits undefined optional filters', async () => {
    (api.get as any).mockResolvedValue({ data: { projects: [], cells: [], months: [] } });
    await accrualApi.cells.grid({ year_from: 2026, year_to: 2026 });
    expect(api.get).toHaveBeenCalledWith('/accrual/grid', {
      params: { year_from: 2026, year_to: 2026 },
    });
  });
});

describe('accrualApi.cells', () => {
  it('listByProject calls GET /accrual/projects/{id}/cells', async () => {
    (api.get as any).mockResolvedValue({ data: [] });
    await accrualApi.cells.listByProject('p1');
    expect(api.get).toHaveBeenCalledWith('/accrual/projects/p1/cells');
  });

  it('redistribute POSTs with body', async () => {
    (api.post as any).mockResolvedValue({ data: { cells_updated: 12 } });
    await accrualApi.cells.redistribute('p1', false);
    expect(api.post).toHaveBeenCalledWith('/accrual/projects/p1/redistribute', { force: false });
  });

  it('redistribute defaults force to false', async () => {
    (api.post as any).mockResolvedValue({ data: { cells_updated: 12 } });
    await accrualApi.cells.redistribute('p1');
    expect(api.post).toHaveBeenCalledWith('/accrual/projects/p1/redistribute', { force: false });
  });

  it('patch PATCHes by id with amount', async () => {
    (api.patch as any).mockResolvedValue({ data: { id: 'c1' } });
    await accrualApi.cells.patch('c1', '250.00');
    expect(api.patch).toHaveBeenCalledWith('/accrual/cells/c1', { amount: '250.00' });
  });

  it('clearOverride DELETEs', async () => {
    (api.delete as any).mockResolvedValue({ data: { id: 'c1' } });
    await accrualApi.cells.clearOverride('c1');
    expect(api.delete).toHaveBeenCalledWith('/accrual/cells/c1/override');
  });

  it('bulk POSTs updates', async () => {
    (api.post as any).mockResolvedValue({ data: { updated: 3 } });
    await accrualApi.cells.bulk([
      { project_id: 'p1', year: 2026, month: 1, amount: '100' },
    ]);
    expect(api.post).toHaveBeenCalledWith('/accrual/cells/bulk', {
      updates: [{ project_id: 'p1', year: 2026, month: 1, amount: '100' }],
    });
  });
});
