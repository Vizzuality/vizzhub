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
    await accrualApi.periods.create({ start_date: '2026-01-01', fx_rates: { USD: '1.10' } });
    expect(api.post).toHaveBeenCalledWith('/accrual/periods', {
      start_date: '2026-01-01',
      fx_rates: { USD: '1.10' },
    });
  });

  it('patch PATCHes by id', async () => {
    (api.patch as any).mockResolvedValue({ data: { id: 'p1' } });
    await accrualApi.periods.patch('p1', { fx_rates: { USD: '1.11' } });
    expect(api.patch).toHaveBeenCalledWith('/accrual/periods/p1', { fx_rates: { USD: '1.11' } });
  });
});
