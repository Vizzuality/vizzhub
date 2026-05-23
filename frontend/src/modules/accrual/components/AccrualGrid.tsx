import { useMemo } from 'react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import type {
  AccrualCell as AccrualCellType,
  AccrualGridMonth,
  AccrualGridProject,
} from '@/modules/accrual/types/accrual';
import {
  buildColumns,
  computeMonthTotals,
  STICKY_LEFT_OFFSETS,
} from '@/modules/accrual/components/AccrualGridColumns';

const STICKY_COL_COUNT = 7;

const fmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export interface AccrualGridProps {
  readonly projects: AccrualGridProject[];
  readonly cells: AccrualCellType[];
  readonly months: AccrualGridMonth[];
  readonly onCellChange: (projectId: string, year: number, month: number, amount: string) => void;
  readonly canEdit?: boolean;
  readonly failedCells?: ReadonlySet<string>;
}

export function AccrualGrid({
  projects,
  cells,
  months,
  onCellChange,
  canEdit = false,
  failedCells,
}: AccrualGridProps): JSX.Element {
  const columns = useMemo(
    () => buildColumns(months, cells, onCellChange, canEdit, failedCells),
    [months, cells, onCellChange, canEdit, failedCells],
  );

  const table = useReactTable({
    data: projects,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const monthTotals = useMemo(
    () => computeMonthTotals(months, projects, cells),
    [months, projects, cells],
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

  return (
    <div
      className="relative overflow-auto rounded-md border"
      style={{ maxHeight: 'calc(100vh - 120px)' }}
      role="grid"
      aria-label="Accrual grid"
    >
      <table className="border-collapse table-fixed" style={{ width: tableWidth }}>
        <colgroup>
          {allColumns.map((col) => (
            <col key={col.id} style={{ width: col.getSize() }} />
          ))}
        </colgroup>
        <thead className="sticky top-0 z-20" style={{ boxShadow: '0 1px 0 hsl(var(--border))' }}>
          {/* Year group row */}
          <tr className="bg-background">
            <th colSpan={STICKY_COL_COUNT} className="sticky left-0 z-20 bg-background" />
            {yearGroups.map(([year, count]) => (
              <th
                key={year}
                colSpan={count}
                className="border-l px-1 py-1 text-center text-xs font-medium text-muted-foreground"
              >
                {year}
              </th>
            ))}
          </tr>
          {/* Column header row */}
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="bg-background">
              {headerGroup.headers.map((header) => {
                const colIdx = header.index;
                const isSticky = colIdx < STICKY_COL_COUNT;
                return (
                  <th
                    key={header.id}
                    className={`px-2 py-1 text-left text-xs font-medium ${
                      isSticky ? 'sticky z-20 bg-background' : 'border-l'
                    }`}
                    style={{
                      width: header.getSize(),
                      left: isSticky ? STICKY_LEFT_OFFSETS[colIdx] : undefined,
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
            <tr key={row.id} className="border-b hover:bg-muted/10">
              {row.getVisibleCells().map((cell) => {
                const colIdx = cell.column.getIndex();
                const isSticky = colIdx < STICKY_COL_COUNT;
                const isNameCol = colIdx === 1;
                return (
                  <td
                    key={cell.id}
                    className={`px-0 py-0 ${
                      isSticky ? 'sticky z-10 bg-background px-2' : 'border-l'
                    } ${isNameCol ? 'max-w-0 overflow-hidden' : ''}`}
                    style={{
                      width: cell.column.getSize(),
                      maxWidth: isNameCol ? cell.column.getSize() : undefined,
                      height: 32,
                      left: isSticky ? STICKY_LEFT_OFFSETS[colIdx] : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        <tfoot className="sticky bottom-0 z-20 bg-background border-t-2">
          <tr>
            <td
              colSpan={STICKY_COL_COUNT}
              className="sticky left-0 z-20 bg-background px-2 py-1 text-xs font-semibold text-muted-foreground"
              style={{ left: 0 }}
            >
              Totals (EUR)
            </td>
            {months.map((m) => {
              const total = monthTotals.get(`${m.year}_${m.month}`) ?? 0;
              return (
                <td
                  key={`total_${m.year}_${m.month}`}
                  className="border-l px-1 py-1 text-right text-xs font-semibold tabular-nums"
                >
                  {fmt.format(total)}
                </td>
              );
            })}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
