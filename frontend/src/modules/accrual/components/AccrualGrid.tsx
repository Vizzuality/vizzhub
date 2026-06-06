import { useMemo } from 'react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridLine,
  AccrualGridMonth,
} from '@/modules/accrual/types/accrual';
import {
  buildColumns,
  computeMonthTotals,
  DEFAULT_STATIC_IDS,
  formatAmount,
  type AccrualSort,
} from '@/modules/accrual/components/AccrualGridColumns';

const ROW_HEIGHT = 36;

export interface AccrualGridProps {
  readonly lines: AccrualGridLine[];
  readonly cells: AccrualCellType[];
  readonly months: AccrualGridMonth[];
  readonly onCellChange: (lineId: string, year: number, month: number, amount: string) => void;
  readonly canEdit?: boolean;
  readonly failedCells?: ReadonlySet<string>;
  readonly onEditLine?: (lineId: string) => void;
  readonly visibleStaticIds?: readonly string[];
  readonly sort?: AccrualSort | null;
  readonly onSort?: (key: string) => void;
  readonly onRateChange?: (lineId: string, rate: string | null) => void;
}

export function AccrualGrid({
  lines,
  cells,
  months,
  onCellChange,
  canEdit = false,
  failedCells,
  onEditLine,
  visibleStaticIds = DEFAULT_STATIC_IDS,
  sort = null,
  onSort,
  onRateChange,
}: AccrualGridProps): JSX.Element {
  const columns = useMemo(
    () =>
      buildColumns(months, cells, onCellChange, canEdit, failedCells, onEditLine, {
        visibleStaticIds,
        sort,
        onSort,
        onRateChange,
      }),
    [months, cells, onCellChange, canEdit, failedCells, onEditLine, visibleStaticIds, sort, onSort, onRateChange],
  );

  const table = useReactTable({
    data: lines,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const monthTotals = useMemo(
    () => computeMonthTotals(months, lines, cells),
    [months, lines, cells],
  );

  // Group months by year for the top header row.
  const yearGroups = useMemo(() => {
    const map = new Map<number, number>();
    for (const m of months) {
      map.set(m.year, (map.get(m.year) ?? 0) + 1);
    }
    return Array.from(map.entries());
  }, [months]);

  // Authoritative column widths consumed both by <colgroup> (forces layout)
  // and by the sticky offset math. `table-fixed` + explicit total width make
  // the column widths load-bearing — without an explicit numeric width the
  // browser falls back to max-content sizing, which lets long codes blow up
  // the first column and breaks every sticky offset downstream.
  const allColumns = table.getAllLeafColumns();
  const tableWidth = allColumns.reduce((sum, c) => sum + c.getSize(), 0);

  // The leading N columns (N = visible static columns) are pinned left. Their
  // left offsets are the running sum of the preceding sticky widths — derived
  // here rather than hardcoded, so hiding a column re-pins the rest correctly.
  const stickyCount = visibleStaticIds.length;
  const nameColIdx = visibleStaticIds.indexOf('name');
  const stickyOffsets = useMemo(() => {
    const offsets: number[] = [];
    let acc = 0;
    for (let i = 0; i < stickyCount; i++) {
      offsets.push(acc);
      acc += allColumns[i]?.getSize() ?? 0;
    }
    return offsets;
  }, [allColumns, stickyCount]);

  return (
    <div
      className="relative overflow-auto overscroll-x-contain rounded-lg border bg-card shadow-sm"
      style={{ maxHeight: 'calc(100vh - 120px)' }}
      role="grid"
      aria-label="Accrual grid"
    >
      <table className="border-collapse table-fixed text-sm" style={{ width: tableWidth }}>
        <colgroup>
          {allColumns.map((col) => (
            <col key={col.id} style={{ width: col.getSize() }} />
          ))}
        </colgroup>
        <thead className="sticky top-0 z-20">
          {/* Totals row — pinned above the column headers */}
          <tr className="border-b-2 bg-card">
            <th
              colSpan={stickyCount}
              className="sticky left-0 z-20 bg-card px-3 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
              style={{ left: 0 }}
            >
              Totals (EUR)
            </th>
            {months.map((m) => (
              <th
                key={`total_${m.year}_${m.month}`}
                className="border-l px-2 py-1.5 text-right text-xs font-semibold tabular-nums"
              >
                {formatAmount(monthTotals.get(`${m.year}_${m.month}`) ?? 0)}
              </th>
            ))}
          </tr>
          {/* Year group row */}
          <tr className="bg-muted">
            <th colSpan={stickyCount} className="sticky left-0 z-20 bg-muted" />
            {yearGroups.map(([year, count]) => (
              <th
                key={year}
                colSpan={count}
                className="border-l px-1 py-1.5 text-center text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {year}
              </th>
            ))}
          </tr>
          {/* Column header row */}
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b bg-muted">
              {headerGroup.headers.map((header) => {
                const colIdx = header.index;
                const isSticky = colIdx < stickyCount;
                const isFirstMonth = colIdx === stickyCount;
                return (
                  <th
                    key={header.id}
                    className={`px-3 py-2 text-left text-[11px] font-semibold text-muted-foreground ${
                      isSticky ? 'sticky z-20 bg-muted' : 'border-l'
                    } ${isFirstMonth ? 'border-l-2 border-l-border' : ''}`}
                    style={{
                      width: header.getSize(),
                      left: isSticky ? stickyOffsets[colIdx] : undefined,
                    }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="group border-b transition-colors hover:bg-muted/40">
              {row.getVisibleCells().map((cell) => {
                const colIdx = cell.column.getIndex();
                const isSticky = colIdx < stickyCount;
                const isNameCol = colIdx === nameColIdx;
                const isFirstMonth = colIdx === stickyCount;
                return (
                  <td
                    key={cell.id}
                    className={`align-middle ${
                      isSticky ? 'sticky z-10 bg-card px-3 group-hover:bg-muted/40' : 'border-l p-0'
                    } ${isNameCol ? 'max-w-0 overflow-hidden' : ''} ${
                      isFirstMonth ? 'border-l-2 border-l-border' : ''
                    }`}
                    style={{
                      width: cell.column.getSize(),
                      maxWidth: isNameCol ? cell.column.getSize() : undefined,
                      height: ROW_HEIGHT,
                      left: isSticky ? stickyOffsets[colIdx] : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
