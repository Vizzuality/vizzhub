import { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type RowData,
} from '@tanstack/react-table';
import { Trash2 } from 'lucide-react';
import { useAuth } from '@/core/hooks/useAuth';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';
import { PlannerAddRow } from '@/modules/capacity/components/PlannerAddRow';
import type { PlannerGroup } from '@/modules/capacity/types/planner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';

declare module '@tanstack/react-table' {
  interface TableMeta<TData extends RowData> {
    updateCell: (
      projectId: string,
      userId: string,
      week: string,
      value: number | null,
    ) => void;
    currentUserId: string;
  }
}

interface FlatRow {
  _type: 'header' | 'data' | 'add';
  groupId: string;
  groupName: string;
  user_id?: string;
  user_name?: string;
  functional_area?: string;
  project_id?: string;
  project_name?: string;
  cells: Record<string, number>;
}

interface PlannerGridProps {
  readonly groups: PlannerGroup[];
  readonly weeks: string[];
  readonly groupBy: string;
  readonly fa: string;
  readonly onCellChange: (
    projectId: string,
    userId: string,
    week: string,
    value: number | null,
  ) => void;
  readonly onDeleteRow: (projectId: string, userId: string) => void;
  readonly onAddRow: (groupId: string, targetId: string) => void;
  readonly addRowOptions: { id: string; name: string; extra?: string }[];
}

function getMonthLabel(weekStr: string): string {
  const d = new Date(weekStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

function getISOWeekNumber(weekStr: string): number {
  const d = new Date(weekStr + 'T00:00:00');
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
}

export function PlannerGrid({
  groups,
  weeks,
  groupBy,
  fa,
  onCellChange,
  onDeleteRow,
  onAddRow,
  addRowOptions,
}: PlannerGridProps): JSX.Element {
  const { user: authUser } = useAuth();

  // Filter by FA if set
  const filteredGroups = useMemo(() => {
    if (fa === 'all') return groups;
    return groups
      .map((g) => ({
        ...g,
        rows: g.rows.filter((r) => r.functional_area === fa),
      }))
      .filter((g) => g.rows.length > 0);
  }, [groups, fa]);

  // Flatten groups into rows for the table
  const flatRows = useMemo((): FlatRow[] => {
    const result: FlatRow[] = [];
    for (const group of filteredGroups) {
      result.push({
        _type: 'header',
        groupId: group.id,
        groupName: group.name,
        cells: {},
      });
      for (const row of group.rows) {
        result.push({
          _type: 'data',
          groupId: group.id,
          groupName: group.name,
          user_id: row.user_id,
          user_name: row.user_name,
          functional_area: row.functional_area,
          project_id: row.project_id,
          project_name: row.project_name,
          cells: row.cells,
        });
      }
      result.push({
        _type: 'add',
        groupId: group.id,
        groupName: group.name,
        cells: {},
      });
    }
    return result;
  }, [filteredGroups]);

  // Group weeks by month for headers
  const monthGroups = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const w of weeks) {
      const label = getMonthLabel(w);
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(w);
    }
    return map;
  }, [weeks]);

  // Existing IDs in each group (for add-row filtering)
  const existingIdsByGroup = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const group of filteredGroups) {
      const ids = new Set<string>();
      for (const row of group.rows) {
        ids.add(groupBy === 'project' ? row.user_id : row.project_id);
      }
      map.set(group.id, ids);
    }
    return map;
  }, [filteredGroups, groupBy]);

  const columns = useMemo((): ColumnDef<FlatRow>[] => {
    const fixed: ColumnDef<FlatRow>[] = [
      {
        id: 'fa',
        header: 'FA',
        size: 50,
        cell: ({ row: { original } }) => {
          if (original._type === 'data') {
            return (
              <span className="text-xs text-muted-foreground">
                {original.functional_area}
              </span>
            );
          }
          return null;
        },
      },
      {
        id: 'name',
        header: groupBy === 'project' ? 'Name' : 'Project',
        size: 200,
        cell: ({ row: { original } }) => {
          if (original._type === 'data') {
            const label =
              groupBy === 'project' ? original.user_name : original.project_name;
            return (
              <div className="flex items-center justify-between gap-1">
                <span className="truncate text-sm">{label}</span>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button
                      className="shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity"
                    >
                      <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Remove row?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will delete all planned allocations for this combination.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() =>
                          onDeleteRow(original.project_id!, original.user_id!)
                        }
                      >
                        Remove
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            );
          }
          return null;
        },
      },
    ];

    const weekCols: ColumnDef<FlatRow>[] = weeks.map((week) => ({
      id: `week_${week}`,
      header: () => <span className="text-xs">W{getISOWeekNumber(week)}</span>,
      size: 42,
      cell: ({ row: { original }, table }) => {
        if (original._type !== 'data') return null;
        const value = original.cells[week];
        const isOwnRow = original.user_id === table.options.meta?.currentUserId;
        return (
          <PlannerCell
            value={value}
            isOwnRow={isOwnRow}
            onChange={(v) =>
              table.options.meta?.updateCell(
                original.project_id!,
                original.user_id!,
                week,
                v,
              )
            }
          />
        );
      },
    }));

    return [...fixed, ...weekCols];
  }, [weeks, groupBy, onDeleteRow, onAddRow, addRowOptions, existingIdsByGroup]);

  const table = useReactTable({
    data: flatRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    meta: {
      updateCell: onCellChange,
      currentUserId: authUser?.id ?? '',
    },
  });

  return (
    <div className="overflow-auto rounded-md border" style={{ maxHeight: 'calc(100vh - 120px)' }}>
      <table className="w-full border-collapse">
        {/* Month header row */}
        <thead className="sticky top-0 z-20">
          <tr className="border-b border-border bg-background">
            <th colSpan={2} className="sticky left-0 z-20 bg-background" />
            {Array.from(monthGroups.entries()).map(([month, monthWeeks]) => (
              <th
                key={month}
                colSpan={monthWeeks.length}
                className="border-l px-1 py-1 text-center text-xs font-medium text-muted-foreground"
              >
                {month}
              </th>
            ))}
          </tr>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b border-border bg-background">
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className={`px-2 py-1 text-left text-xs font-medium ${
                    header.index < 2 ? 'sticky left-0 z-20 bg-background' : ''
                  }`}
                  style={{
                    width: header.getSize(),
                    left: header.index < 2
                      ? header.index === 0 ? 0 : 50
                      : undefined,
                  }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isHeader = row.original._type === 'header';
            const isAdd = row.original._type === 'add';
            const weekCells = row.getVisibleCells().slice(2);

            if (isHeader) {
              return (
                <tr key={row.id} className="group/row border-b bg-muted">
                  <td
                    colSpan={2}
                    className="sticky left-0 z-10 bg-muted px-2 py-1 whitespace-nowrap"
                    style={{ left: 0 }}
                  >
                    <span className="font-semibold text-sm">{row.original.groupName}</span>
                  </td>
                  {weekCells.map((cell) => (
                    <td key={cell.id} className="border-l bg-muted" style={{ height: 28 }} />
                  ))}
                </tr>
              );
            }

            if (isAdd) {
              return (
                <tr key={row.id} className="group/row border-b">
                  <td
                    colSpan={2}
                    className="sticky left-0 z-10 bg-background px-2 py-0"
                    style={{ left: 0, height: 28 }}
                  >
                    <PlannerAddRow
                      options={addRowOptions}
                      existingIds={existingIdsByGroup.get(row.original.groupId) ?? new Set()}
                      onSelect={(id) => onAddRow(row.original.groupId, id)}
                      label={groupBy === 'project' ? 'Add person' : 'Add project'}
                    />
                  </td>
                  {weekCells.map((cell) => (
                    <td key={cell.id} className="border-l" style={{ height: 28 }} />
                  ))}
                </tr>
              );
            }

            return (
              <tr key={row.id} className="group/row border-b hover:bg-muted/10">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`px-0 py-0 ${
                      cell.column.getIndex() < 2
                        ? 'sticky left-0 z-10 bg-background px-2'
                        : 'border-l'
                    }`}
                    style={{
                      width: cell.column.getSize(),
                      height: 32,
                      left: cell.column.getIndex() < 2
                        ? cell.column.getIndex() === 0 ? 0 : 50
                        : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
