import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { AlertTriangle, MessageSquare, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { shortMonth } from '@/shared/constants/dates';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';
import { PlannerAddRow } from '@/modules/capacity/components/PlannerAddRow';
import { currentMondayString } from '@/modules/capacity/utils/plannerDates';
import type { PlannerGroup } from '@/modules/capacity/types/planner';

const CURRENT_WEEK_BORDER_LIGHT = '1px solid #2d8a4e';
const CURRENT_WEEK_BORDER_DARK = '1px solid #5AFF15';
const CURRENT_WEEK_TINT_LIGHT = 'rgba(45, 138, 78, 0.10)';
const CURRENT_WEEK_TINT_DARK = 'rgba(90, 255, 21, 0.08)';
import {
  useCellSelection,
  type CellCoord,
} from '@/modules/capacity/hooks/useCellSelection';
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

interface FlatRow {
  _type: 'header' | 'data' | 'add';
  groupId: string;
  groupName: string;
  hasWarning?: boolean;
  user_id?: string;
  user_name?: string;
  functional_area?: string;
  project_id?: string;
  project_name?: string;
  is_absence?: boolean;
  is_other?: boolean;
  cells: Record<string, number>;
  comments?: Record<string, string>;
}

interface PlannerGridProps {
  readonly groups: PlannerGroup[];
  readonly weeks: string[];
  readonly warnings: string[];
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
  readonly onCommentChange?: (
    projectId: string,
    userId: string,
    week: string,
    comment: string | null,
  ) => void;
  readonly addRowOptions: { id: string; name: string; extra?: string }[];
}

function getISOWeekNumber(weekStr: string): number {
  const d = new Date(weekStr + 'T00:00:00');
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
}

const STICKY_LEFT: Record<number, number> = { 0: 0, 1: 50 };
function stickyLeft(colIdx: number): number | undefined {
  return STICKY_LEFT[colIdx];
}

function FACellRenderer({ row }: { readonly row: FlatRow }): JSX.Element | null {
  if (row._type === 'data') {
    return (
      <span className="text-xs text-muted-foreground">
        {row.functional_area}
      </span>
    );
  }
  return null;
}

function NameCellRenderer({
  row,
  groupBy,
  warningSet,
  onDeleteRow,
}: {
  readonly row: FlatRow;
  readonly groupBy: string;
  readonly warningSet: Set<string>;
  readonly onDeleteRow: (projectId: string, userId: string) => void;
}): JSX.Element | null {
  if (row._type !== 'data') return null;

  const isPinned = row.is_absence || row.is_other;
  const defaultLabel = groupBy === 'project' ? row.user_name : row.project_name;
  const label = isPinned && row.is_other ? 'Others' : defaultLabel;
  const userHasWarning = row.user_id ? warningSet.has(row.user_id) : false;

  return (
    <div className="flex items-center justify-between gap-1">
      <span className="flex items-center gap-1 truncate">
        {groupBy === 'project' && userHasWarning && (
          <span title="Allocations exceed 100%"><AlertTriangle className="h-3 w-3 shrink-0 text-yellow-500" /></span>
        )}
        {groupBy === 'user' && !isPinned ? (
          <Link
            to={`/tracker/projects/${row.project_id}`}
            className="truncate text-sm hover:underline"
          >
            {label}
          </Link>
        ) : (
          <span className={`truncate text-sm ${isPinned ? 'italic text-muted-foreground' : ''}`}>
            {label}
          </span>
        )}
      </span>
      {!isPinned && (
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
                onClick={() => {
                  if (row.project_id && row.user_id) {
                    onDeleteRow(row.project_id, row.user_id);
                  }
                }}
              >
                Remove
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

export function PlannerGrid({
  groups,
  weeks,
  warnings,
  groupBy,
  fa,
  onCellChange,
  onDeleteRow,
  onCommentChange,
  onAddRow,
  addRowOptions,
}: PlannerGridProps): JSX.Element {
  const { user: authUser } = useAuth();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const oddMonthBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)';
  const oddMonthBgMuted = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

  const warningSet = useMemo(() => new Set(warnings), [warnings]);
  const currentWeekKey = useMemo(() => currentMondayString(), []);
  const currentWeekTint = isDark ? CURRENT_WEEK_TINT_DARK : CURRENT_WEEK_TINT_LIGHT;
  const currentWeekBorder = isDark ? CURRENT_WEEK_BORDER_DARK : CURRENT_WEEK_BORDER_LIGHT;
  const [expandedWeek, setExpandedWeek] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const selection = useCellSelection();
  const [batchDraft, setBatchDraft] = useState('');
  const [showBatchInput, setShowBatchInput] = useState(false);
  const batchInputRef = useRef<HTMLInputElement>(null);
  const copiedValueRef = useRef<number | null>(null);

  // Filter by FA if set
  const filteredGroups = useMemo(() => {
    if (fa === 'all') return groups;
    if (groupBy === 'user') {
      return groups.filter((g) => g.functional_area === fa);
    }
    return groups
      .map((g) => ({
        ...g,
        rows: g.rows.filter((r) => r.functional_area === fa),
      }))
      .filter((g) => g.rows.length > 0);
  }, [groups, fa, groupBy]);

  // Flatten groups into rows for the table
  const flatRows = useMemo((): FlatRow[] => {
    const result: FlatRow[] = [];
    for (const group of filteredGroups) {
      const groupHasWarning = groupBy === 'user'
        ? warningSet.has(group.id)
        : group.rows.some((r) => warningSet.has(r.user_id));
      result.push({
        _type: 'header',
        groupId: group.id,
        groupName: group.name,
        hasWarning: groupHasWarning,
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
          is_absence: row.is_absence,
          is_other: row.is_other,
          cells: row.cells,
          comments: row.comments ?? {},
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
  }, [filteredGroups, groupBy, warningSet]);

  const weeksWithComments = useMemo(() => {
    const set = new Set<string>();
    if (groupBy !== 'user') return set;
    for (const row of flatRows) {
      if (row._type !== 'data' || !row.comments) continue;
      for (const [week, text] of Object.entries(row.comments)) {
        if (text) set.add(week);
      }
    }
    return set;
  }, [flatRows, groupBy]);

  useEffect(() => {
    if (expandedWeek && !weeksWithComments.has(expandedWeek)) {
      setExpandedWeek(null);
    }
  }, [expandedWeek, weeksWithComments]);

  // Build allCoords for selection range calculation
  useEffect(() => {
    const coords: CellCoord[] = [];
    for (const row of flatRows) {
      if (row._type !== 'data') continue;
      for (const week of weeks) {
        coords.push({
          projectId: row.project_id!,
          userId: row.user_id!,
          week,
        });
      }
    }
    selection.allCoordsRef.current = coords;
  }, [flatRows, weeks, selection.allCoordsRef]);

  // Global mouseup to end drag
  useEffect(() => {
    const handler = (): void => selection.handleMouseUp();
    globalThis.addEventListener('mouseup', handler);
    return () => globalThis.removeEventListener('mouseup', handler);
  }, [selection.handleMouseUp]);

  // Apply batch value to selected cells
  const applyBatchValue = useCallback(
    (value: number | null): void => {
      for (const key of selection.selected) {
        const [projectId, userId, week] = key.split(':');
        onCellChange(projectId, userId, week, value);
      }
      selection.clearSelection();
      setShowBatchInput(false);
      setBatchDraft('');
    },
    [selection, onCellChange],
  );

  // Lookup cell value by key
  const cellValueMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of flatRows) {
      if (row._type !== 'data') continue;
      for (const [week, val] of Object.entries(row.cells)) {
        map.set(`${row.project_id}:${row.user_id}:${week}`, val);
      }
    }
    return map;
  }, [flatRows]);

  // Keyboard handler for grid
  const handleGridKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      if (selection.selected.size === 0) return;
      if (showBatchInput) return;

      const isMod = e.metaKey || e.ctrlKey;

      if (isMod && e.key === 'c') {
        e.preventDefault();
        if (selection.selected.size === 1) {
          const key = [...selection.selected][0];
          copiedValueRef.current = cellValueMap.get(key) ?? null;
        }
        return;
      }

      if (isMod && e.key === 'v') {
        e.preventDefault();
        if (copiedValueRef.current !== null) {
          applyBatchValue(copiedValueRef.current);
        }
        return;
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        applyBatchValue(null);
        return;
      }

      if (e.key === 'Escape') {
        selection.clearSelection();
        setExpandedWeek(null);
        return;
      }

      // Typing a digit opens batch input
      if (/^\d$/.test(e.key) && selection.selected.size > 1) {
        e.preventDefault();
        setBatchDraft(e.key);
        setShowBatchInput(true);
      }
    },
    [selection, showBatchInput, applyBatchValue, cellValueMap],
  );

  // Focus batch input when it appears
  useEffect(() => {
    if (showBatchInput) batchInputRef.current?.focus();
  }, [showBatchInput]);

  const handleBatchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>): void => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const num = Number.parseInt(batchDraft, 10);
        if (!Number.isNaN(num) && num > 0) {
          applyBatchValue(Math.min(num, 200));
        } else {
          setShowBatchInput(false);
          setBatchDraft('');
        }
      } else if (e.key === 'Escape') {
        setShowBatchInput(false);
        setBatchDraft('');
      }
    },
    [batchDraft, applyBatchValue],
  );

  // Group weeks by month + track month index for alternating backgrounds
  const { monthGroups, weekMonthInfo } = useMemo(() => {
    const groups = new Map<string, string[]>();
    const info = new Map<string, { isOddMonth: boolean }>();
    let prevMonth = '';
    let monthIdx = 0;
    for (const w of weeks) {
      const month = shortMonth(w);
      if (!groups.has(month)) groups.set(month, []);
      groups.get(month)!.push(w);
      if (month !== prevMonth) {
        if (prevMonth !== '') monthIdx++;
        prevMonth = month;
      }
      info.set(w, { isOddMonth: monthIdx % 2 === 1 });
    }
    return { monthGroups: groups, weekMonthInfo: info };
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
        cell: ({ row: { original } }) => <FACellRenderer row={original} />,
      },
      {
        id: 'name',
        header: groupBy === 'project' ? 'Name' : 'Project',
        size: 200,
        cell: ({ row: { original } }) => (
          <NameCellRenderer
            row={original}
            groupBy={groupBy}
            warningSet={warningSet}
            onDeleteRow={onDeleteRow}
          />
        ),
      },
    ];

    const weekCols: ColumnDef<FlatRow>[] = weeks.map((week) => {
      const weekLabel = `W${getISOWeekNumber(week)}`;
      return {
        id: `week_${week}`,
        header: () => (
          <div className="flex items-center gap-1">
            <span>{weekLabel}</span>
            {weeksWithComments.has(week) && (
              <button
                type="button"
                aria-label={`Toggle comments for ${weekLabel}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedWeek((prev) => (prev === week ? null : week));
                }}
                className={`rounded p-0.5 ${expandedWeek === week ? 'text-primary' : 'text-muted-foreground hover:text-primary'}`}
              >
                <MessageSquare className="h-3 w-3" />
              </button>
            )}
          </div>
        ),
        size: 42,
        cell: () => null,
      };
    });

    return [...fixed, ...weekCols];
  }, [weeks, groupBy, onDeleteRow, warningSet, weeksWithComments, expandedWeek]);

  const table = useReactTable({
    data: flatRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div
      ref={containerRef}
      className="relative overflow-auto rounded-md border"
      style={{ maxHeight: 'calc(100vh - 120px)' }}
      role="grid"
      aria-label="Capacity planner"
      tabIndex={0}
      onKeyDown={handleGridKeyDown}
    >
      {showBatchInput && (
        <div className="absolute left-1/2 top-12 z-50 -translate-x-1/2 rounded-md border bg-background p-2 shadow-lg">
          <label className="mb-1 block text-xs text-muted-foreground">
            Set {selection.selected.size} cells to:
          </label>
          <input
            ref={batchInputRef}
            className="w-20 rounded border px-2 py-1 text-center text-sm outline-none"
            value={batchDraft}
            onChange={(e) => setBatchDraft(e.target.value)}
            onKeyDown={handleBatchKeyDown}
            onBlur={() => { setShowBatchInput(false); setBatchDraft(''); }}
            type="number"
            min={1}
            max={200}
          />
        </div>
      )}
      <table className="w-full border-collapse">
        {/* Month header row */}
        <thead className="sticky top-0 z-20" style={{ boxShadow: '0 1px 0 hsl(var(--border))' }}>
          <tr className="bg-background">
            <th colSpan={2} className="sticky left-0 z-20 bg-background" />
            {Array.from(monthGroups.entries()).map(([month, monthWeeks], idx) => (
              <th
                key={month}
                colSpan={monthWeeks.length}
                className="border-l px-1 py-1 text-center text-xs font-medium text-muted-foreground"
                style={idx % 2 === 1 ? { backgroundColor: oddMonthBg } : undefined}
              >
                {month}
              </th>
            ))}
          </tr>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="bg-background">
              {headerGroup.headers.map((header) => {
                const weekIdx = header.index - 2;
                const isWeekHeader = header.index >= 2;
                const weekKey = isWeekHeader ? weeks[weekIdx] : undefined;
                const info = weekKey ? weekMonthInfo.get(weekKey) : undefined;
                const isCurrentWeek = weekKey === currentWeekKey;
                const headerBg = isCurrentWeek
                  ? currentWeekTint
                  : info?.isOddMonth ? oddMonthBg : undefined;
                return (
                  <th
                    key={header.id}
                    className={`px-2 py-1 text-left text-xs font-medium ${
                      header.index < 2
                        ? 'sticky left-0 z-20 bg-background'
                        : 'border-l'
                    }`}
                    style={{
                      width: header.getSize(),
                      left: stickyLeft(header.index),
                      backgroundColor: headerBg,
                      borderLeft: isCurrentWeek ? currentWeekBorder : undefined,
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
          {table.getRowModel().rows.map((row) => {
            const isHeader = row.original._type === 'header';
            const isAdd = row.original._type === 'add';
            const weekCells = row.getVisibleCells().slice(2);

            if (isHeader) {
              return (
                <tr key={row.id} className="group/row border-b bg-muted">
                  <td
                    colSpan={2}
                    className="sticky left-0 z-10 bg-muted px-2 py-1 max-w-0 truncate"
                    style={{ left: 0, maxWidth: 250 }}
                  >
                    <span className="flex items-center gap-1">
                      {row.original.hasWarning && (
                        <span title="Allocations exceed 100%"><AlertTriangle className="h-3.5 w-3.5 shrink-0 text-yellow-500" /></span>
                      )}
                      {groupBy === 'project' ? (
                        <Link
                          to={`/tracker/projects/${row.original.groupId}`}
                          className="truncate font-semibold text-sm hover:underline"
                          title={row.original.groupName}
                        >
                          {row.original.groupName}
                        </Link>
                      ) : (
                        <span className="truncate font-semibold text-sm">{row.original.groupName}</span>
                      )}
                    </span>
                  </td>
                  {weekCells.map((cell) => {
                    const weekKey = weeks[cell.column.getIndex() - 2];
                    const info = weekMonthInfo.get(weekKey);
                    const isCurrentWeek = weekKey === currentWeekKey;
                    return (
                      <td
                        key={cell.id}
                        className="border-l bg-muted"
                        style={{
                          height: 28,
                          backgroundColor: isCurrentWeek
                            ? currentWeekTint
                            : info?.isOddMonth ? oddMonthBgMuted : undefined,
                          borderLeft: isCurrentWeek ? currentWeekBorder : undefined,
                        }}
                      />
                    );
                  })}
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
                  {weekCells.map((cell) => {
                    const weekKey = weeks[cell.column.getIndex() - 2];
                    const info = weekMonthInfo.get(weekKey);
                    const isCurrentWeek = weekKey === currentWeekKey;
                    return (
                      <td
                        key={cell.id}
                        className="border-l"
                        style={{
                          height: 28,
                          backgroundColor: isCurrentWeek
                            ? currentWeekTint
                            : info?.isOddMonth ? oddMonthBg : undefined,
                          borderLeft: isCurrentWeek ? currentWeekBorder : undefined,
                        }}
                      />
                    );
                  })}
                </tr>
              );
            }

            const orig = row.original;
            const commentForExpanded = expandedWeek && orig.comments
              ? orig.comments[expandedWeek]
              : undefined;
            return (
              <tr key={row.id} className="group/row border-b hover:bg-muted/10">
                {row.getVisibleCells().map((cell) => {
                  const colIdx = cell.column.getIndex();
                  const isWeekCol = colIdx >= 2;
                  const weekIdx = colIdx - 2;
                  const week = isWeekCol ? weeks[weekIdx] : undefined;
                  const coord: CellCoord | undefined =
                    isWeekCol && orig.project_id && orig.user_id && week
                      ? { projectId: orig.project_id, userId: orig.user_id, week }
                      : undefined;
                  const isSelected = coord ? selection.isSelected(coord) : false;

                  const showOverlay = isWeekCol && week === expandedWeek && commentForExpanded;
                  return (
                    <td
                      key={cell.id}
                      className={`group/cell px-0 py-0 ${
                        colIdx < 2
                          ? 'sticky left-0 z-10 bg-background px-2'
                          : 'border-l'
                      }`}
                      style={{
                        position: 'relative',
                        width: cell.column.getSize(),
                        height: 32,
                        left: stickyLeft(colIdx),
                        backgroundColor: isWeekCol && week === currentWeekKey
                          ? currentWeekTint
                          : isWeekCol && week && weekMonthInfo.get(week)?.isOddMonth
                            ? oddMonthBg : undefined,
                        borderLeft: isWeekCol && week === currentWeekKey
                          ? currentWeekBorder : undefined,
                      }}
                    >
                      {isWeekCol && orig._type === 'data' && coord ? (
                        <PlannerCell
                          value={orig.cells[coord.week]}
                          isOwnRow={orig.user_id === authUser?.id}
                          selected={isSelected}
                          absence={orig.is_absence}
                          canComment={groupBy === 'user' && !orig.is_absence && !orig.is_other}
                          comment={orig.comments?.[coord.week]}
                          onCommentChange={(text) =>
                            onCommentChange?.(coord.projectId, coord.userId, coord.week, text)
                          }
                          onChange={(v) =>
                            onCellChange(
                              coord.projectId,
                              coord.userId,
                              coord.week,
                              v,
                            )
                          }
                          onMouseDown={(e) => {
                            selection.handleCellMouseDown(coord, e.shiftKey);
                          }}
                          onMouseEnter={() => {
                            selection.handleCellMouseEnter(coord);
                          }}
                        />
                      ) : (
                        flexRender(cell.column.columnDef.cell, cell.getContext())
                      )}
                      {showOverlay && (
                        <div
                          aria-hidden
                          className="pointer-events-none absolute top-0 flex h-full items-center rounded-sm border px-2 text-xs shadow-sm"
                          style={{
                            left: '100%',
                            width: 4 * 42,
                            backgroundColor: isDark ? '#451a03' : '#fffbeb',
                            color: isDark ? '#fef3c7' : '#78350f',
                            borderColor: '#d97706',
                            zIndex: 25,
                          }}
                          title={commentForExpanded}
                        >
                          <span className="truncate">{commentForExpanded}</span>
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
