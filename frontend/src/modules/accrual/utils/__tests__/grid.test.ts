import { describe, it, expect } from 'vitest';
import { filterLinesBySearch, sortLines } from '@/modules/accrual/utils/grid';
import type { AccrualGridLine } from '@/modules/accrual/types/accrual';

function makeLine(overrides: Partial<AccrualGridLine>): AccrualGridLine {
  return {
    id: 'l',
    name: 'Line',
    source: 'excel',
    excel_code: 'A.1',
    value_eur: '100',
    value_orig: null,
    currency: null,
    window_start: null,
    window_end: null,
    projects: [],
    health: { status: 'ok', diff_eur: '0', diff_pct: 0 },
    data_quality_note: null,
    dates_diverged: false,
    rate: null,
    ...overrides,
  };
}

describe('filterLinesBySearch', () => {
  const lines = [
    makeLine({ id: 'a', name: 'Coastal Atlas', excel_code: 'CA.1' }),
    makeLine({
      id: 'b',
      name: 'Forest Map',
      excel_code: 'FM.1',
      projects: [
        {
          id: 'p1',
          code: 'TREE-9',
          name: 'Tree Cover',
          status: 'live',
          project_manager_id: null,
          project_manager_name: null,
        },
      ],
    }),
  ];

  it('returns all lines for an empty query', () => {
    expect(filterLinesBySearch(lines, '   ')).toHaveLength(2);
  });

  it('matches on the line name (case-insensitive)', () => {
    expect(filterLinesBySearch(lines, 'forest').map((l) => l.id)).toEqual(['b']);
  });

  it('matches on a linked project code', () => {
    expect(filterLinesBySearch(lines, 'tree-9').map((l) => l.id)).toEqual(['b']);
  });

  it('matches on the line code', () => {
    expect(filterLinesBySearch(lines, 'ca.1').map((l) => l.id)).toEqual(['a']);
  });
});

describe('sortLines', () => {
  const lines = [
    makeLine({ id: 'a', name: 'Banana', value_eur: '300', excel_code: 'B' }),
    makeLine({ id: 'b', name: 'Apple', value_eur: '100', excel_code: 'A' }),
    makeLine({ id: 'c', name: 'Cherry', value_eur: '200', excel_code: 'C' }),
  ];

  it('is a no-op when sort is null', () => {
    expect(sortLines(lines, null)).toBe(lines);
  });

  it('sorts numerically by value_eur ascending', () => {
    expect(sortLines(lines, { key: 'value_eur', dir: 'asc' }).map((l) => l.value_eur)).toEqual([
      '100',
      '200',
      '300',
    ]);
  });

  it('sorts by name descending', () => {
    expect(sortLines(lines, { key: 'name', dir: 'desc' }).map((l) => l.name)).toEqual([
      'Cherry',
      'Banana',
      'Apple',
    ]);
  });

  it('does not mutate the input array', () => {
    const copy = [...lines];
    sortLines(lines, { key: 'code', dir: 'asc' });
    expect(lines).toEqual(copy);
  });
});
