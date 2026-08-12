import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  formatPeriod,
  formatShortPeriod,
  generateMonthRange,
  periodKey,
  getYearOptions,
  getMonthsSinceStart,
  formatRelativeTime,
} from '../dateUtils';

describe('dateUtils', () => {
  describe('formatPeriod', () => {
    it('formats period as "Mon YYYY"', () => {
      expect(formatPeriod(2024, 1)).toBe('Jan 2024');
      expect(formatPeriod(2024, 12)).toBe('Dec 2024');
      expect(formatPeriod(2023, 6)).toBe('Jun 2023');
    });
  });

  describe('formatShortPeriod', () => {
    it('formats period as "Mon \'YY"', () => {
      expect(formatShortPeriod(2024, 1)).toBe("Jan '24");
      expect(formatShortPeriod(2024, 12)).toBe("Dec '24");
      expect(formatShortPeriod(2023, 6)).toBe("Jun '23");
    });
  });

  describe('generateMonthRange', () => {
    it('generates range from start to end date', () => {
      const range = generateMonthRange('2024-01-01', '2024-03-31');
      expect(range).toEqual([
        { year: 2024, month: 1 },
        { year: 2024, month: 2 },
        { year: 2024, month: 3 },
      ]);
    });

    it('handles year boundary', () => {
      const range = generateMonthRange('2023-11-01', '2024-02-28');
      expect(range).toEqual([
        { year: 2023, month: 11 },
        { year: 2023, month: 12 },
        { year: 2024, month: 1 },
        { year: 2024, month: 2 },
      ]);
    });

    it('returns single month when start equals end', () => {
      const range = generateMonthRange('2024-05-15', '2024-05-20');
      expect(range).toEqual([{ year: 2024, month: 5 }]);
    });
  });

  describe('periodKey', () => {
    it('creates unique key from year and month', () => {
      expect(periodKey(2024, 1)).toBe('2024-1');
      expect(periodKey(2024, 12)).toBe('2024-12');
    });
  });

  describe('getYearOptions', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-06-15'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('returns current year and past years in descending order', () => {
      const years = getYearOptions(3);
      expect(years).toEqual([2024, 2023, 2022, 2021]);
    });

    it('respects custom pastYears parameter', () => {
      const years = getYearOptions(1);
      expect(years).toEqual([2024, 2023]);
    });

    it('defaults to 3 past years', () => {
      const years = getYearOptions();
      expect(years).toHaveLength(4);
    });
  });

  describe('getMonthsSinceStart', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-06-15'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('returns minMonths when startDate is null', () => {
      expect(getMonthsSinceStart(null)).toBe(12);
    });

    it('returns minMonths when startDate is undefined', () => {
      expect(getMonthsSinceStart(undefined)).toBe(12);
    });

    it('calculates months since start', () => {
      expect(getMonthsSinceStart('2024-01-01')).toBe(12);
      expect(getMonthsSinceStart('2023-06-01')).toBe(13);
    });

    it('clamps to minMonths', () => {
      expect(getMonthsSinceStart('2024-05-01', 12, 36)).toBe(12);
    });

    it('clamps to maxMonths', () => {
      expect(getMonthsSinceStart('2020-01-01', 12, 36)).toBe(36);
    });

    it('accepts custom min/max values', () => {
      expect(getMonthsSinceStart('2024-05-01', 6, 24)).toBe(6);
    });
  });

  describe('formatRelativeTime', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-06-15T12:00:00Z'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('returns "just now" for times less than 1 minute ago', () => {
      expect(formatRelativeTime('2024-06-15T11:59:30Z')).toBe('just now');
    });

    it('returns minutes ago for times less than 1 hour ago', () => {
      expect(formatRelativeTime('2024-06-15T11:55:00Z')).toBe('5m ago');
      expect(formatRelativeTime('2024-06-15T11:30:00Z')).toBe('30m ago');
    });

    it('returns hours ago for times less than 24 hours ago', () => {
      expect(formatRelativeTime('2024-06-15T10:00:00Z')).toBe('2h ago');
      expect(formatRelativeTime('2024-06-14T18:00:00Z')).toBe('18h ago');
    });

    it('returns days ago for times less than 7 days ago', () => {
      expect(formatRelativeTime('2024-06-14T12:00:00Z')).toBe('1d ago');
      expect(formatRelativeTime('2024-06-10T12:00:00Z')).toBe('5d ago');
    });

    it('returns locale date string for times 7+ days ago', () => {
      const result = formatRelativeTime('2024-06-01T12:00:00Z');
      expect(result).toMatch(/\d/);
    });
  });
});
