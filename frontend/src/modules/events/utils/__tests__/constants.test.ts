import { describe, expect, it } from 'vitest';
import { buildYearOptions } from '../constants';

describe('buildYearOptions', () => {
  it('returns the years with events, newest first', () => {
    expect(buildYearOptions([2024, 2027, 2025])).toEqual(['2027', '2025', '2024']);
  });

  it('includes a future year that has events (regression: was capped at currentYear)', () => {
    expect(buildYearOptions([2027])).toContain('2027');
  });

  it('keeps the current selection even when that year has no events', () => {
    expect(buildYearOptions([2025], '2023')).toEqual(['2025', '2023']);
  });

  it('does not duplicate the selection when it already has events', () => {
    expect(buildYearOptions([2025, 2024], '2025')).toEqual(['2025', '2024']);
  });

  it('returns an empty list when there are no events and no selection', () => {
    expect(buildYearOptions()).toEqual([]);
  });
});
