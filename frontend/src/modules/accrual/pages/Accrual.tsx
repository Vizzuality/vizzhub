import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus } from 'lucide-react';
import { useAccrualGrid } from '@/modules/accrual/hooks/useAccrualGrid';
import { useAccrualMutations } from '@/modules/accrual/hooks/useAccrualMutations';
import { AccrualGrid } from '@/modules/accrual/components/AccrualGrid';
import { AccrualToolbar } from '@/modules/accrual/components/AccrualToolbar';
import type { AccrualFilters } from '@/modules/accrual/components/AccrualToolbar';
import {
  STATIC_COLUMNS,
  type AccrualSort,
} from '@/modules/accrual/components/AccrualGridColumns';
import { AccrualLineEditor } from '@/modules/accrual/components/AccrualLineEditor';
import { filterLinesBySearch, sortLines } from '@/modules/accrual/utils/grid';
import { Button } from '@/shared/components/ui/button';
import { useLocalStorage } from '@/shared/hooks/useLocalStorage';
import { usePermission, Action } from '@/core/permissions';

const CURRENT_YEAR = new Date().getFullYear();

// localStorage keys for grid preferences that persist across sessions.
const HIDDEN_COLUMNS_KEY = 'accrual.grid.hiddenColumns';
const COLLAPSED_KEY = 'accrual.grid.collapsed';
const SORT_KEY = 'accrual.grid.sort';

// Creation order mirrors the original Excel seed, so it is the natural default.
const DEFAULT_SORT: AccrualSort = { key: 'created_at', dir: 'asc' };

// When collapsed, only the Line column stays pinned so the month grid gets the
// horizontal room — critical on laptop-width screens.
const COLLAPSED_STATIC_IDS: readonly string[] = ['name'];

function clampYear(year: number, min: number, max: number): number {
  return Math.max(min, Math.min(year, max));
}

export function Accrual(): JSX.Element {
  const [filters, setFilters] = useState<AccrualFilters>({
    year_from: CURRENT_YEAR,
    year_to: CURRENT_YEAR,
    issues_only: false,
    search: '',
  });
  const [hiddenColumnIds, setHiddenColumnIds] = useLocalStorage<string[]>(
    HIDDEN_COLUMNS_KEY,
    [],
  );
  const [collapsed, setCollapsed] = useLocalStorage<boolean>(COLLAPSED_KEY, false);
  const [sort, setSort] = useLocalStorage<AccrualSort>(SORT_KEY, DEFAULT_SORT);

  const hiddenColumns = useMemo(() => new Set(hiddenColumnIds), [hiddenColumnIds]);

  // Collapsed → Line only; otherwise the user's selected (non-hidden) columns.
  const visibleStaticIds = useMemo(() => {
    if (collapsed) return COLLAPSED_STATIC_IDS;
    return STATIC_COLUMNS.filter((c) => !hiddenColumns.has(c.id)).map((c) => c.id);
  }, [collapsed, hiddenColumns]);

  const toggleColumn = (id: string): void => {
    setHiddenColumnIds((prev) => {
      const next = new Set(prev);
      // Guard against hiding the last visible column — keep at least one.
      if (next.has(id)) next.delete(id);
      else if (prev.length < STATIC_COLUMNS.length - 1) next.add(id);
      return [...next];
    });
  };

  const handleSort = (key: string): void => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    );
  };

  const apiFilters = useMemo(
    () => ({ year_from: filters.year_from, year_to: filters.year_to }),
    [filters.year_from, filters.year_to],
  );

  const { data, isLoading, error } = useAccrualGrid(apiFilters);
  const { updateCell, failedCells, errorMessage, setLineRate } = useAccrualMutations();
  const canEdit = usePermission(Action.ACCRUAL_MANAGE);
  // null = editor closed; 'new' = create mode; otherwise the line id being edited.
  const [editingLineId, setEditingLineId] = useState<string | null>(null);

  // One-shot snap on first response: if the saved filter is outside the
  // data's range, fold it back in so the user lands on actual data.
  const snappedRef = useRef(false);
  useEffect(() => {
    if (snappedRef.current || !data?.bounds) return;
    snappedRef.current = true;
    const { min_year, max_year } = data.bounds;
    setFilters((prev) => {
      const yf = clampYear(prev.year_from, min_year, max_year);
      const yt = clampYear(prev.year_to, min_year, max_year);
      if (yf === prev.year_from && yt === prev.year_to) return prev;
      return { ...prev, year_from: yf, year_to: Math.max(yt, yf) };
    });
  }, [data?.bounds]);

  const handleCellChange = async (
    lineId: string,
    year: number,
    month: number,
    amount: string,
  ): Promise<void> => {
    // Upsert by (line, year, month): editing an empty month creates the cell.
    await updateCell(lineId, year, month, amount);
  };

  // Lines with at least one non-zero cell in the visible range. The grid
  // endpoint already clips cells by [year_from, year_to], so a simple set
  // suffices — no extra date check.
  const linesWithCells = useMemo(() => {
    if (!data) return new Set<string>();
    const ids = new Set<string>();
    for (const c of data.cells) {
      if (c.line_id && Number(c.amount) !== 0) ids.add(c.line_id);
    }
    return ids;
  }, [data]);

  const visibleLines = useMemo(() => {
    if (!data) return [];
    let result = data.lines.filter((l) => linesWithCells.has(l.id));
    if (filters.issues_only) {
      result = result.filter(
        (l) => l.health.status === 'critical' || l.health.status === 'warning',
      );
    }
    result = filterLinesBySearch(result, filters.search);
    return sortLines(result, sort);
  }, [data, linesWithCells, filters.issues_only, filters.search, sort]);

  const issuesCount = useMemo(
    () =>
      visibleLines.filter((l) => l.health.status === 'critical' || l.health.status === 'warning')
        .length,
    [visibleLines],
  );

  function renderGrid(): JSX.Element {
    if (error) return <p className="text-sm text-destructive">Failed to load grid.</p>;
    if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
    if (visibleLines.length === 0) {
      const msg = filters.search.trim()
        ? 'No lines match the filter.'
        : 'No accrual lines with data in this range.';
      return <p className="text-sm text-muted-foreground">{msg}</p>;
    }
    return (
      <AccrualGrid
        lines={visibleLines}
        cells={data?.cells ?? []}
        months={data?.months ?? []}
        onCellChange={handleCellChange}
        canEdit={canEdit}
        failedCells={failedCells}
        onEditLine={canEdit ? setEditingLineId : undefined}
        visibleStaticIds={visibleStaticIds}
        sort={sort}
        onSort={handleSort}
        onRateChange={canEdit ? setLineRate : undefined}
      />
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual grid</h1>
        {canEdit && (
          <Button size="sm" onClick={() => setEditingLineId('new')}>
            <Plus className="mr-1 h-4 w-4" />
            New line
          </Button>
        )}
      </div>
      <AccrualToolbar
        filters={filters}
        onChange={setFilters}
        minYear={data?.bounds?.min_year}
        maxYear={data?.bounds?.max_year}
        hiddenColumns={hiddenColumns}
        onToggleColumn={toggleColumn}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        sort={sort}
        onSortChange={setSort}
      />
      {issuesCount > 0 && !filters.issues_only && (
        <button
          type="button"
          onClick={() => setFilters((f) => ({ ...f, issues_only: true }))}
          className="w-full rounded border border-amber-300 bg-amber-50 px-3 py-2 text-left text-sm text-amber-900 hover:bg-amber-100"
        >
          <strong>{issuesCount}</strong> line{issuesCount === 1 ? '' : 's'} need{issuesCount === 1 ? 's' : ''} review — click to filter
        </button>
      )}
      {errorMessage && (
        <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}
      {renderGrid()}
      {canEdit && editingLineId !== null && (
        <AccrualLineEditor lineId={editingLineId} onClose={() => setEditingLineId(null)} />
      )}
    </div>
  );
}
