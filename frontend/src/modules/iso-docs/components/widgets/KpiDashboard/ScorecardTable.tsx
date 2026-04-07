import { useState } from 'react';
import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import { buildScorecardRows, GLOBAL_WEIGHT_KEYS, DIMENSION_DEFINITIONS, monthToDataKey } from './constants';
import { periodKey } from './useKpiDashboard';
import { AddKpiDialog } from './AddKpiDialog';
import {
  useCreateRegistryRow,
  useUpdateRegistryRow,
  useDeleteRegistryRow,
} from '../../../hooks/useRegistryRows';
import type { MonthColumn } from './types';
import type { RegistryRow } from '../../../types/registry';
import type { GlobalMetricsRecord, ScoringConfig } from '@/modules/scorecard/types';

interface ScorecardTableProps {
  readonly months: MonthColumn[];
  readonly metricsByPeriod: Map<string, GlobalMetricsRecord>;
  readonly globalWeights: ScoringConfig['global_weights'];
  readonly targets: ScoringConfig['targets'];
  readonly manualRows: RegistryRow[];
  readonly nodeId: string;
  readonly isEditor: boolean;
  readonly selectedYear: number;
}

function scoreColor(value: number | null, level: 0 | 1 | 2): string {
  if (value === null) return '';
  if (level === 2) return '';

  if (value >= 80) return 'text-green-600 dark:text-green-400';
  if (value >= 60) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function extractValue(
  record: GlobalMetricsRecord,
  key: string,
  level: 0 | 1 | 2,
): number | null {
  if (level === 0) {
    const s = record.scores.score;
    if (!s || s.count === 0) return null;
    return s.value !== null ? Math.round(s.value * 10) / 10 : null;
  }
  if (level === 1) {
    const scores = record.scores as unknown as Record<string, { value: number | null; count: number }>;
    const entry = scores[key];
    if (!entry || entry.count === 0) return null;
    return entry.value !== null ? Math.round(entry.value * 10) / 10 : null;
  }
  const indicators = record.indicators as unknown as Record<string, { value: number | null; count: number }>;
  const entry = indicators[key];
  if (!entry || entry.count === 0) return null;
  const v = entry.value;
  return v !== null ? Math.round(v * 10) / 10 : null;
}

function getWeight(
  key: string,
  level: 0 | 1 | 2,
  globalWeights: ScoringConfig['global_weights'],
): string {
  if (level !== 1) return '';
  const weightKey = GLOBAL_WEIGHT_KEYS[key];
  if (!weightKey) return '';
  const weights = globalWeights as Record<string, number>;
  const w = weights[weightKey];
  if (w === undefined) return '';
  return `${Math.round(w * 100)}%`;
}

function getTarget(
  key: string,
  level: 0 | 1 | 2,
  targets: ScoringConfig['targets'],
): string {
  if (level <= 1) return '80';
  const t = (targets as Record<string, number | undefined>)[key];
  if (t === undefined) return '';
  return String(t);
}

interface EditingCell {
  rowId: string;
  monthKey: string;
  value: string;
}

export function ScorecardTable({
  months,
  metricsByPeriod,
  globalWeights,
  targets,
  manualRows,
  nodeId,
  isEditor,
  selectedYear,
}: ScorecardTableProps): React.ReactElement {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);

  const createRow = useCreateRegistryRow(nodeId);
  const updateRow = useUpdateRegistryRow(nodeId);
  const deleteRow = useDeleteRegistryRow(nodeId);

  const allRows = buildScorecardRows();
  const visibleRows = allRows.filter((row) => {
    if (row.level !== 2) return true;
    return !collapsed.has(row.parentKey ?? '');
  });

  function toggleDimension(key: string): void {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleAdd(data: Record<string, unknown>): void {
    createRow.mutate(
      { data, year: selectedYear },
      { onSuccess: () => setDialogOpen(false) },
    );
  }

  function handleCellClick(rowId: string, monthKey: string, currentValue: unknown): void {
    if (!isEditor) return;
    setEditingCell({
      rowId,
      monthKey,
      value: currentValue !== null && currentValue !== undefined ? String(currentValue) : '',
    });
  }

  function handleCellSave(row: RegistryRow): void {
    if (!editingCell) return;
    const numericValue = editingCell.value === '' ? null : Number(editingCell.value);
    updateRow.mutate({
      rowId: row.id,
      data: { data: { ...row.data, [editingCell.monthKey]: numericValue } },
    });
    setEditingCell(null);
  }

  function handleCellKeyDown(e: React.KeyboardEvent, row: RegistryRow): void {
    if (e.key === 'Enter') handleCellSave(row);
    else if (e.key === 'Escape') setEditingCell(null);
  }

  const dimensionKeys = new Set(DIMENSION_DEFINITIONS.map((d) => d.key));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b">
            <th className="sticky left-0 z-10 bg-background text-left px-3 py-2 font-semibold min-w-[220px]">
              Name
            </th>
            <th className="text-left px-3 py-2 font-semibold min-w-[200px]">Description</th>
            <th className="text-left px-3 py-2 font-semibold min-w-[200px]">Formula</th>
            <th className="text-center px-3 py-2 font-semibold w-16">Target</th>
            <th className="text-center px-3 py-2 font-semibold w-16">Weight</th>
            {months.map((m) => (
              <th key={`${m.year}-${m.month}`} className="text-center px-2 py-2 font-semibold min-w-[64px]">
                {m.label}
              </th>
            ))}
            {isEditor && <th className="w-10" />}
          </tr>
        </thead>
        <tbody>
          {/* Scorecard rows (read-only) */}
          {visibleRows.map((row) => {
            const isDimension = dimensionKeys.has(row.key);
            const isCollapsed = collapsed.has(row.key);
            const rowKey = row.level === 2 ? `${row.parentKey}__${row.key}` : row.key;

            return (
              <tr
                key={rowKey}
                className={cn('border-b hover:bg-muted/20 transition-colors', {
                  'font-bold bg-muted/30': row.level === 0,
                  'font-semibold cursor-pointer': row.level === 1,
                })}
                onClick={isDimension ? () => toggleDimension(row.key) : undefined}
              >
                <td
                  className={cn(
                    'sticky left-0 z-10 bg-background px-3 py-2',
                    row.level === 0 && 'font-bold',
                    row.level === 2 && 'pl-8 text-muted-foreground',
                  )}
                >
                  <span className="flex items-center gap-1">
                    {isDimension && (
                      <span className="shrink-0">
                        {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      </span>
                    )}
                    {row.name}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{row.description}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{row.formula}</td>
                <td className="px-3 py-2 text-center">{getTarget(row.key, row.level, targets)}</td>
                <td className="px-3 py-2 text-center">{getWeight(row.key, row.level, globalWeights)}</td>
                {months.map((m) => {
                  const record = metricsByPeriod.get(periodKey(m.year, m.month));
                  const value = record ? extractValue(record, row.key, row.level) : null;
                  return (
                    <td
                      key={`${m.year}-${m.month}`}
                      className={cn('px-2 py-2 text-center tabular-nums', value !== null && scoreColor(value, row.level))}
                    >
                      {value !== null ? value : '—'}
                    </td>
                  );
                })}
                {isEditor && <td />}
              </tr>
            );
          })}

          {/* Manual KPI rows (editable) */}
          {manualRows.map((row) => (
            <tr key={row.id} className="border-b hover:bg-muted/20 transition-colors">
              <td className="sticky left-0 z-10 bg-background px-3 py-2 font-medium">
                {String(row.data.name ?? '—')}
              </td>
              <td className="px-3 py-2 text-xs text-muted-foreground">
                {String(row.data.methodology ?? '—')}
              </td>
              <td className="px-3 py-2 text-xs text-muted-foreground">
                {String(row.data.formula ?? '—')}
              </td>
              <td className="px-3 py-2 text-center">
                {row.data.target != null ? String(row.data.target) : '—'}
              </td>
              <td className="px-3 py-2 text-center" />
              {months.map((m) => {
                const monthKey = monthToDataKey(m.month);
                const cellValue = row.data[monthKey];
                const isEditing = editingCell?.rowId === row.id && editingCell?.monthKey === monthKey;

                return (
                  <td
                    key={`${m.year}-${m.month}`}
                    className="px-2 py-2 text-center tabular-nums"
                    onClick={() => handleCellClick(row.id, monthKey, cellValue)}
                  >
                    {isEditing ? (
                      <input
                        type="number"
                        step="any"
                        className="w-16 text-center border rounded px-1 py-0.5 text-sm bg-background"
                        value={editingCell.value}
                        onChange={(e) =>
                          setEditingCell((prev) => prev ? { ...prev, value: e.target.value } : prev)
                        }
                        onBlur={() => handleCellSave(row)}
                        onKeyDown={(e) => handleCellKeyDown(e, row)}
                        autoFocus
                      />
                    ) : (
                      <span className={cn(isEditor && 'cursor-pointer hover:text-foreground')}>
                        {cellValue != null ? String(cellValue) : '—'}
                      </span>
                    )}
                  </td>
                );
              })}
              {isEditor && (
                <td className="px-2 py-2 text-center">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6"
                    onClick={() => deleteRow.mutate(row.id)}
                    aria-label="Delete KPI row"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {isEditor && (
        <div className="flex justify-end mt-2">
          <Button size="sm" variant="outline" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-1" /> Add KPI
          </Button>
        </div>
      )}

      <AddKpiDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleAdd}
        isLoading={createRow.isPending}
      />
    </div>
  );
}
