import { describe, it, expect } from 'vitest';
import { queryKeys } from '@/core/hooks/queryKeys';

describe('queryKeys', () => {
  describe('accrual', () => {
    it('exposes periods query keys', () => {
      expect(queryKeys.accrual.periods.all).toEqual(['accrual', 'periods']);
      expect(queryKeys.accrual.periods.list()).toEqual(['accrual', 'periods', 'list']);
      expect(queryKeys.accrual.periods.current()).toEqual(['accrual', 'periods', 'current']);
      expect(queryKeys.accrual.periods.detail('p1')).toEqual(['accrual', 'periods', 'p1']);
    });

    it('exposes cells query keys', () => {
      expect(queryKeys.accrual.cells.all).toEqual(['accrual', 'cells']);
      expect(queryKeys.accrual.cells.grid({ status: 'pending' })).toEqual([
        'accrual',
        'cells',
        'grid',
        { status: 'pending' },
      ]);
    });

    it('exposes dashboard query keys', () => {
      expect(queryKeys.accrual.dashboard.monthly({ year: 2026 })).toEqual([
        'accrual',
        'dashboard',
        'monthly',
        { year: 2026 },
      ]);
      expect(queryKeys.accrual.dashboard.byProject({ status: 'active' })).toEqual([
        'accrual',
        'dashboard',
        'by-project',
        { status: 'active' },
      ]);
    });
  });
});
