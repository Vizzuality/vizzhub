import type { AccrualGridLine } from '@/modules/accrual/types/accrual';
import type { AccrualSort } from '@/modules/accrual/components/AccrualGridColumns';

// Filter lines by a free-text query matched against the line code/name and any
// linked project's code or name. Empty/whitespace query is a no-op.
export function filterLinesBySearch(
  lines: AccrualGridLine[],
  query: string,
): AccrualGridLine[] {
  const q = query.trim().toLowerCase();
  if (!q) return lines;
  return lines.filter((line) => {
    const haystack = [
      line.excel_code,
      line.name,
      ...line.projects.flatMap((p) => [p.code, p.name]),
    ];
    return haystack.some((v) => v?.toLowerCase().includes(q));
  });
}

function sortValue(line: AccrualGridLine, key: string): string | number {
  switch (key) {
    case 'value_eur':
      return Number(line.value_eur) || 0;
    case 'code':
      return (line.excel_code ?? '').toLowerCase();
    case 'name':
      return (line.name ?? '').toLowerCase();
    default:
      return '';
  }
}

// Stable sort by the given key/direction. Returns the input untouched when no
// sort is active. Numeric keys compare numerically; everything else by locale.
export function sortLines(
  lines: AccrualGridLine[],
  sort: AccrualSort | null,
): AccrualGridLine[] {
  if (!sort) return lines;
  const { key, dir } = sort;
  const factor = dir === 'asc' ? 1 : -1;
  return [...lines].sort((a, b) => {
    const av = sortValue(a, key);
    const bv = sortValue(b, key);
    let cmp: number;
    if (typeof av === 'number' && typeof bv === 'number') {
      cmp = av - bv;
    } else {
      cmp = String(av).localeCompare(String(bv));
    }
    return cmp * factor;
  });
}
