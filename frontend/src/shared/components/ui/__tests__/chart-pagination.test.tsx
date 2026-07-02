import { describe, it, expect } from 'vitest';
import {
  chartPageCount,
  latestChartPage,
  useChartPagination,
} from '@/shared/components/ui/chart-pagination';
import { renderHook } from '@testing-library/react';

describe('chartPageCount / latestChartPage', () => {
  it('returns 1 page (index 0) for empty data', () => {
    expect(chartPageCount(0)).toBe(1);
    expect(latestChartPage(0)).toBe(0);
  });

  it('returns 1 page for exactly the window size', () => {
    expect(chartPageCount(6)).toBe(1);
    expect(latestChartPage(6)).toBe(0);
  });

  it('returns 2 pages when one over the window', () => {
    expect(chartPageCount(7)).toBe(2);
    expect(latestChartPage(7)).toBe(1);
  });

  it('returns the last page index for a multi-window dataset', () => {
    expect(chartPageCount(18)).toBe(3);
    expect(latestChartPage(18)).toBe(2);
  });

  it('honours a custom page size', () => {
    expect(chartPageCount(25, 10)).toBe(3);
    expect(latestChartPage(25, 10)).toBe(2);
  });
});

describe('useChartPagination', () => {
  it('returns empty visible, totalPages=1, safePage=0 for empty data', () => {
    const { result } = renderHook(() => useChartPagination<number>([], 0));
    expect(result.current.visible).toEqual([]);
    expect(result.current.totalPages).toBe(1);
    expect(result.current.safePage).toBe(0);
  });

  it('returns the oldest window when seeded with page 0 (7 items)', () => {
    const data = [1, 2, 3, 4, 5, 6, 7];
    const { result } = renderHook(() => useChartPagination(data, 0));
    expect(result.current.totalPages).toBe(2);
    expect(result.current.safePage).toBe(0);
    expect(result.current.visible).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('returns the latest window when seeded with latestChartPage (7 items)', () => {
    const data = [1, 2, 3, 4, 5, 6, 7];
    const { result } = renderHook(() =>
      useChartPagination(data, latestChartPage(data.length)),
    );
    expect(result.current.totalPages).toBe(2);
    expect(result.current.safePage).toBe(1);
    expect(result.current.visible).toEqual([7]);
  });

  it('clamps page below 0 to 0', () => {
    const { result } = renderHook(() => useChartPagination([1, 2, 3], -5));
    expect(result.current.safePage).toBe(0);
  });

  it('clamps page above totalPages-1', () => {
    const { result } = renderHook(() => useChartPagination([1, 2, 3, 4, 5, 6, 7], 99));
    expect(result.current.safePage).toBe(1);
    expect(result.current.visible).toEqual([7]);
  });

  it('windows by a custom page size', () => {
    const data = Array.from({ length: 25 }, (_, i) => i + 1);
    const { result } = renderHook(() => useChartPagination(data, 1, 10));
    expect(result.current.totalPages).toBe(3);
    expect(result.current.visible).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
  });
});
