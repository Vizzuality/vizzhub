import { describe, it, expect, vi, beforeEach } from 'vitest';
import { accrualApi } from '@/modules/accrual/services/accrual';
import api from '@/core/services/client';

vi.mock('@/core/services/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

describe('accrualApi.periods', () => {
  it('list calls GET /api/accrual/periods', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] });
    await accrualApi.periods.list();
    expect(api.get).toHaveBeenCalledWith('/accrual/periods');
  });

  it('current calls GET /api/accrual/periods/current', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: null });
    await accrualApi.periods.current();
    expect(api.get).toHaveBeenCalledWith('/accrual/periods/current');
  });

  it('create POSTs the payload', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { id: 'p1' } });
    await accrualApi.periods.create({ start_date: '2026-01-01' });
    expect(api.post).toHaveBeenCalledWith('/accrual/periods', {
      start_date: '2026-01-01',
    });
  });
});

describe('accrualApi.cells.grid', () => {
  it('GETs /accrual/grid with filter params', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { projects: [], cells: [], months: [] } });
    await accrualApi.cells.grid({ year_from: 2026, year_to: 2026, status: 'live' });
    expect(api.get).toHaveBeenCalledWith('/accrual/grid', {
      params: { year_from: 2026, year_to: 2026, status: 'live' },
    });
  });

  it('omits undefined optional filters', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { projects: [], cells: [], months: [] } });
    await accrualApi.cells.grid({ year_from: 2026, year_to: 2026 });
    expect(api.get).toHaveBeenCalledWith('/accrual/grid', {
      params: { year_from: 2026, year_to: 2026 },
    });
  });
});

describe('accrualApi.cells', () => {
  it('patch PATCHes by id with amount', async () => {
    vi.mocked(api.patch).mockResolvedValue({ data: { id: 'c1' } });
    await accrualApi.cells.patch('c1', '250.00');
    expect(api.patch).toHaveBeenCalledWith('/accrual/cells/c1', { amount: '250.00' });
  });

  it('upsertOnLine PUTs (line, year, month, amount)', async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { id: 'c1' } });
    await accrualApi.cells.upsertOnLine('l1', 2026, 7, '500.00');
    expect(api.put).toHaveBeenCalledWith('/accrual/lines/l1/cells', {
      year: 2026,
      month: 7,
      amount: '500.00',
    });
  });

  it('clearOverride DELETEs', async () => {
    vi.mocked(api.delete).mockResolvedValue({ data: { id: 'c1' } });
    await accrualApi.cells.clearOverride('c1');
    expect(api.delete).toHaveBeenCalledWith('/accrual/cells/c1/override');
  });

  it('bulk POSTs line-keyed updates', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { updated: 3 } });
    await accrualApi.cells.bulk([{ line_id: 'l1', year: 2026, month: 1, amount: '100' }]);
    expect(api.post).toHaveBeenCalledWith('/accrual/cells/bulk', {
      updates: [{ line_id: 'l1', year: 2026, month: 1, amount: '100' }],
    });
  });
});

describe('accrualApi.lines', () => {
  it('redistribute POSTs with body', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { cells_updated: 12 } });
    await accrualApi.lines.redistribute('l1', false);
    expect(api.post).toHaveBeenCalledWith('/accrual/lines/l1/redistribute', { force: false });
  });

  it('redistribute defaults force to false', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { cells_updated: 12 } });
    await accrualApi.lines.redistribute('l1');
    expect(api.post).toHaveBeenCalledWith('/accrual/lines/l1/redistribute', { force: false });
  });
});
