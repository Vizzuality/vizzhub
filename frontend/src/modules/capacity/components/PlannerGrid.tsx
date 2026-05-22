import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';
import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { shortMonth } from '@/shared/constants/dates';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';
import { PlannerAddRow } from '@/modules/capacity/components/PlannerAddRow';
import { currentMondayString } from '@/modules/capacity/utils/plannerDates';
import {
  useCellSelection,
  type CellCoord,
} from '@/shared/hooks/useCellSelection';
import type { PlannerGroup } from '@/modules/capacity/types/planner';
import {
  CURRENT_WEEK_BORDER_DARK,
  CURRENT_WEEK_BORDER_LIGHT,
  CURRENT_WEEK_TINT_DARK,
  CURRENT_WEEK_TINT_LIGHT,
  mondayDayLabel,
  stickyLeft,
  weekCellStyle,
  type WeekStyleConfig,
} from '@/shared/components/grid/stickyGridStyles';
import {
  CommentOverlay,
  FACell,
  NameCell,
  WeekHeader,
  type FlatRow,
  type NameColumnMeta,
  type WeekColumnMeta,
} from '@/modules/capacity/components/PlannerGridColumns';

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
  readonly canEdit?: boolean;
  readonly failedCells?: ReadonlySet<string>;
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
  canEdit = false,
  failedCells,
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
  const toggleWeek = useCallback((week: string): void => {
    setExpandedWeek((prev) => (prev === week ? null : week));
  }, []);

  const containerRef = useRef<HTMLDivElement>(null);
  const selection = useCellSelection();
  const [batchDraft, setBatchDraft] = useState('');
  const [showBatchInput, setShowBatchInput] = useState(false);
  const batchInputRef = useRef<HTMLInputElement>(null);
  const copiedValueRef = useRef<number | null>(null);

  // When the user lacks write permission, every mutation entry-point becomes
  // a no-op. We still pass handlers down so cell rendering / hover behaviour
  // stays consistent, but the actual table state never changes.
  const gatedCellChange = canEdit ? onCellChange : (() => undefined);
  const gatedDeleteRow = canEdit ? onDeleteRow : (() => undefined);
  const gatedCommentChange = canEdit ? onCommentChange : undefined;
  const gatedAddRow = canEdit ? onAddRow : (() => undefined);

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

  const flatRows = useMemo((): FlatRow[] => {
    const result: FlatRow[] = [];
    for (const group of filteredGroups) {
      const groupHasWarning = groupBy === 'user'
        ? warningSet.has(group.id)
        : group.rows.some((r) => warningSet.has(r.user_id));
      let weekSums: Record<string, number> | undefined;
      if (groupBy === 'user') {
        weekSums = {};
        for (const row of group.rows) {
          for (const [week, val] of Object.entries(row.cells)) {
            weekSums[week] = (weekSums[week] ?? 0) + val;
          }
        }
      }
      result.push({
        _type: 'header',
        groupId: group.id,
        groupName: group.name,
        hasWarning: groupHasWarning,
        cells: {},
        weekSums,
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
    for (const row of flatRows) {
      if (row._type !== 'data' || !row.comments) continue;
      for (const [week, text] of Object.entries(row.comments)) {
        if (text) set.add(week);
      }
    }
    return set;
  }, [flatRows]);

  useEffect(() => {
    if (expandedWeek && !weeksWithComments.has(expandedWeek)) {
      setExpandedWeek(null);
    }
  }, [expandedWeek, weeksWithComments]);

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

  useEffect(() => {
    const handler = (): void => selection.handleMouseUp();
    globalThis.addEventListener('mouseup', handler);
    return () => globalThis.removeEventListener('mouseup', handler);
  }, [selection.handleMouseUp]);

  const applyBatchValue = useCallback(
    (value: number | null): void => {
      for (const key of selection.selected) {
        const [projectId, userId, week] = key.split(':');
        gatedCellChange(projectId, userId, week, value);
      }
      selection.clearSelection();
      setShowBatchInput(false);
      setBatchDraft('');
    },
    [selection, gatedCellChange],
  );

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

      if (/^\d$/.test(e.key) && selection.selected.size > 1) {
        e.preventDefault();
        setBatchDraft(e.key);
        setShowBatchInput(true);
      }
    },
    [selection, showBatchInput, applyBatchValue, cellValueMap],
  );

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

  const { monthGroups, weekMonthInfo } = useMemo(() => {
    const monthMap = new Map<string, string[]>();
    const info = new Map<string, { isOddMonth: boolean }>();
    let prevMonth = '';
    let monthIdx = 0;
    for (const w of weeks) {
      const month = shortMonth(w);
      if (!monthMap.has(month)) monthMap.set(month, []);
      monthMap.get(month)!.push(w);
      if (month !== prevMonth) {
        if (prevMonth !== '') monthIdx++;
        prevMonth = month;
      }
      info.set(w, { isOddMonth: monthIdx % 2 === 1 });
    }
    return { monthGroups: monthMap, weekMonthInfo: info };
  }, [weeks]);

  const weekStyleConfig: WeekStyleConfig = {
    currentWeekKey, currentWeekTint, currentWeekBorder, oddMonthBg, weekMonthInfo,
  };
  const weekStyleConfigMuted: WeekStyleConfig = {
    ...weekStyleConfig, oddMonthBg: oddMonthBgMuted,
  };

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
        cell: FACell,
      },
      {
        id: 'name',
        header: groupBy === 'project' ? 'Name' : 'Project',
        size: 200,
        cell: NameCell,
        meta: { groupBy, warningSet, onDeleteRow: gatedDeleteRow } satisfies NameColumnMeta,
      },
    ];

    const weekCols: ColumnDef<FlatRow>[] = weeks.map((week) => ({
      id: `week_${week}`,
      header: WeekHeader,
      size: 42,
      cell: () => null,
      meta: {
        week,
        weekLabel: mondayDayLabel(week),
        hasComment: weeksWithComments.has(week),
        isExpanded: expandedWeek === week,
        onToggle: toggleWeek,
      } satisfies WeekColumnMeta,
    }));

    return [...fixed, ...weekCols];
  }, [weeks, groupBy, gatedDeleteRow, warningSet, weeksWithComments, expandedWeek, toggleWeek]);

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
                const weekKey = header.index >= 2 ? weeks[header.index - 2] : undefined;
                const wStyle = weekKey ? weekCellStyle(weekKey, weekStyleConfig) : {};
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
                      ...wStyle,
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
                    const sum = row.original.weekSums?.[weekKey];
                    const overAllocated = sum !== undefined && sum > 100;
                    return (
                      <td
                        key={cell.id}
                        className="border-l bg-muted text-center text-xs tabular-nums"
                        style={{ height: 28, ...weekCellStyle(weekKey, weekStyleConfigMuted) }}
                      >
                        {sum !== undefined && sum > 0 && (
                          <span
                            className={
                              overAllocated
                                ? 'font-semibold text-yellow-600 dark:text-yellow-400'
                                : 'text-muted-foreground'
                            }
                          >
                            {sum}
                          </span>
                        )}
                      </td>
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
                      onSelect={(id) => gatedAddRow(row.original.groupId, id)}
                      label={groupBy === 'project' ? 'Add person' : 'Add project'}
                    />
                  </td>
                  {weekCells.map((cell) => {
                    const weekKey = weeks[cell.column.getIndex() - 2];
                    return (
                      <td
                        key={cell.id}
                        className="border-l"
                        style={{ height: 28, ...weekCellStyle(weekKey, weekStyleConfig) }}
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
                  const week = isWeekCol ? weeks[colIdx - 2] : undefined;
                  const coord: CellCoord | undefined =
                    isWeekCol && orig.project_id && orig.user_id && week
                      ? { projectId: orig.project_id, userId: orig.user_id, week }
                      : undefined;
                  const isSelected = coord ? selection.isSelected(coord) : false;
                  const wStyle = isWeekCol && week
                    ? weekCellStyle(week, weekStyleConfig) : {};

                  const isNameCol = colIdx === 1;
                  return (
                    <td
                      key={cell.id}
                      className={`group/cell px-0 py-0 ${
                        colIdx < 2
                          ? 'sticky left-0 z-10 bg-background px-2'
                          : 'border-l'
                      } ${isNameCol ? 'max-w-0 overflow-hidden' : ''}`}
                      style={{
                        position: isWeekCol ? 'relative' : undefined,
                        width: cell.column.getSize(),
                        maxWidth: isNameCol ? cell.column.getSize() : undefined,
                        height: 32,
                        left: stickyLeft(colIdx),
                        ...wStyle,
                      }}
                    >
                      {isWeekCol && orig._type === 'data' && coord ? (
                        <PlannerCell
                          value={orig.cells[coord.week]}
                          isOwnRow={orig.user_id === authUser?.id}
                          selected={isSelected}
                          hasError={
                            failedCells?.has(
                              `${coord.projectId}:${coord.userId}:${coord.week}`,
                            ) ?? false
                          }
                          canComment
                          comment={orig.comments?.[coord.week]}
                          onCommentChange={(text) =>
                            gatedCommentChange?.(coord.projectId, coord.userId, coord.week, text)
                          }
                          onChange={(v) =>
                            gatedCellChange(
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
                      {isWeekCol && week === expandedWeek && commentForExpanded && (
                        <CommentOverlay comment={commentForExpanded} isDark={isDark} />
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
