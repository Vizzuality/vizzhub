import { describe, it, expect, vi, afterEach } from 'vitest';
import { isSnapshotStale } from '../isoStaleCheck';

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

describe('isSnapshotStale', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns true when capturedAt is null', () => {
    expect(isSnapshotStale(null)).toBe(true);
  });

  it('returns true when capturedAt is more than 35 days ago', () => {
    const now = new Date('2026-02-23T12:00:00Z').getTime();
    vi.spyOn(Date, 'now').mockReturnValue(now);

    const fortyDaysAgo = new Date(now - 40 * ONE_DAY_MS).toISOString();
    expect(isSnapshotStale(fortyDaysAgo)).toBe(true);
  });

  it('returns false when capturedAt is within 35 days', () => {
    const now = new Date('2026-02-23T12:00:00Z').getTime();
    vi.spyOn(Date, 'now').mockReturnValue(now);

    const tenDaysAgo = new Date(now - 10 * ONE_DAY_MS).toISOString();
    expect(isSnapshotStale(tenDaysAgo)).toBe(false);
  });

  it('returns false when capturedAt is today', () => {
    const now = new Date('2026-02-23T12:00:00Z').getTime();
    vi.spyOn(Date, 'now').mockReturnValue(now);

    const today = new Date(now).toISOString();
    expect(isSnapshotStale(today)).toBe(false);
  });

  it('returns true when capturedAt is exactly 36 days ago', () => {
    const now = new Date('2026-02-23T12:00:00Z').getTime();
    vi.spyOn(Date, 'now').mockReturnValue(now);

    const thirtySixDaysAgo = new Date(now - 36 * ONE_DAY_MS).toISOString();
    expect(isSnapshotStale(thirtySixDaysAgo)).toBe(true);
  });
});
