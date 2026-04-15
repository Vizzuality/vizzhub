import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addMonths,
  defaultStart,
  endFromStart,
} from '@/modules/capacity/utils/plannerDates';

// UTC-safe weekday check: the helpers emit a YYYY-MM-DD that must be Monday
// regardless of the host timezone. Parsing via Date.UTC avoids local drift.
function isMondayUTC(dateStr: string): boolean {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay() === 1;
}

describe('plannerDates', () => {
  describe('addMonths', () => {
    it('snaps to Monday when moving one month back', () => {
      // 2026-04-13 Monday W16 → prev month → 2026-03-09 Monday W11
      expect(addMonths('2026-04-13', -1)).toBe('2026-03-09');
    });

    it('snaps to Monday when moving one month forward', () => {
      // 2026-04-13 Monday W16 → next month → 2026-05-11 Monday W20
      expect(addMonths('2026-04-13', 1)).toBe('2026-05-11');
    });

    it('crosses year boundary going backward', () => {
      // 2026-01-05 Monday W2 → prev month → 2025-12-01 Monday
      expect(addMonths('2026-01-05', -1)).toBe('2025-12-01');
    });

    it('handles setMonth rollover when target month is shorter', () => {
      // 2026-03-30 Monday → prev month would land on "Feb 30" which rolls to
      // early March; snap must still return a valid Monday.
      const result = addMonths('2026-03-30', -1);
      expect(isMondayUTC(result)).toBe(true);
    });

    it('reproduces the W10-empty-column scenario without TZ drift', () => {
      // Before the fix, calling addMonths('2026-04-06', -1) in timezones east
      // of UTC emitted '2026-03-01' (Sunday) instead of '2026-03-02' (Mon W10),
      // which made the backend weeks list include W10 but exclude its data.
      expect(addMonths('2026-04-06', -1)).toBe('2026-03-02');
      expect(isMondayUTC(addMonths('2026-04-06', -1))).toBe(true);
    });

    it('always returns a Monday across a full year of moves', () => {
      let cursor = '2026-01-05';
      for (let i = 0; i < 12; i++) {
        cursor = addMonths(cursor, 1);
        expect(isMondayUTC(cursor)).toBe(true);
      }
    });
  });

  describe('defaultStart', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('returns the Monday 6 weeks before the current Monday', () => {
      // Pin "now" to Wed 2026-04-15 → current Monday is 2026-04-13 →
      // minus 6 weeks = 2026-03-02 (Monday W10).
      vi.setSystemTime(new Date(2026, 3, 15, 10, 0, 0));
      expect(defaultStart()).toBe('2026-03-02');
      expect(isMondayUTC(defaultStart())).toBe(true);
    });

    it('snaps to Monday when today is Sunday', () => {
      // 2026-04-12 is Sunday → current week's Monday is 2026-04-06 →
      // minus 6 weeks = 2026-02-23.
      vi.setSystemTime(new Date(2026, 3, 12, 10, 0, 0));
      expect(defaultStart()).toBe('2026-02-23');
      expect(isMondayUTC(defaultStart())).toBe(true);
    });
  });

  describe('endFromStart', () => {
    it('returns start + 6 months snapped to Monday', () => {
      expect(endFromStart('2026-03-02')).toBe(addMonths('2026-03-02', 6));
      expect(isMondayUTC(endFromStart('2026-03-02'))).toBe(true);
    });
  });
});
