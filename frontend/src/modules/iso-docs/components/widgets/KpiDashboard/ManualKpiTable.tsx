import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/lib/utils';
import { monthToDataKey } from './constants';
import { AddKpiDialog } from './AddKpiDialog';
import {
  useCreateRegistryRow,
  useUpdateRegistryRow,
  useDeleteRegistryRow,
} from '../../../hooks/useRegistryRows';
import type { MonthColumn } from './types';
import type { RegistryRow } from '../../../types/registry';

interface ManualKpiTableProps {
  readonly nodeId: string;
  readonly months: MonthColumn[];
  readonly rows: RegistryRow[];
  readonly isEditor: boolean;
  readonly selectedYear: number;
}

const FIXED_COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'scope', label: 'Scope' },
  { key: 'responsible', label: 'Responsible' },
  { key: 'methodology', label: 'Methodology' },
  { key: 'formula', label: 'Formula' },
  { key: 'target', label: 'Target' },
  { key: 'periodicity', label: 'Periodicity' },
] as const;

interface EditingCell {
  rowId: string;
  monthKey: string;
  value: string;
}

export function ManualKpiTable({
  nodeId,
  months,
  rows,
  isEditor,
  selectedYear,
}: ManualKpiTableProps): React.ReactElement {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);

  const createRow = useCreateRegistryRow(nodeId);
  const updateRow = useUpdateRegistryRow(nodeId);
  const deleteRow = useDeleteRegistryRow(nodeId);

  function handleAdd(data: Record<string, unknown>): void {
    createRow.mutate(
      { data, year: selectedYear },
      { onSuccess: () => setDialogOpen(false) },
    );
  }

  function handleCellClick(rowId: string, monthKey: string, currentValue: unknown): void {
    if (!isEditor) return;
    const strValue = currentValue !== null && currentValue !== undefined ? String(currentValue) : '';
    setEditingCell({ rowId, monthKey, value: strValue });
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
    if (e.key === 'Enter') {
      handleCellSave(row);
    } else if (e.key === 'Escape') {
      setEditingCell(null);
    }
  }

  function handleDelete(rowId: string): void {
    deleteRow.mutate(rowId);
  }

  function formatCellValue(value: unknown): string {
    if (value === null || value === undefined) return '—';
    return String(value);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">KPIs Manuales</h3>
        {isEditor && (
          <Button size="sm" variant="outline" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add KPI
          </Button>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">No manual KPIs yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b">
                {FIXED_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      'text-left px-3 py-2 font-semibold whitespace-nowrap',
                      col.key === 'name' && 'sticky left-0 z-10 bg-background min-w-[160px]',
                      col.key === 'methodology' && 'min-w-[200px]',
                    )}
                  >
                    {col.label}
                  </th>
                ))}
                {months.map((m) => (
                  <th
                    key={`${m.year}-${m.month}`}
                    className="text-center px-2 py-2 font-semibold min-w-[64px] whitespace-nowrap"
                  >
                    {m.label}
                  </th>
                ))}
                {isEditor && <th className="px-2 py-2 w-10" />}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b hover:bg-muted/20 transition-colors">
                  {FIXED_COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'px-3 py-2',
                        col.key === 'name' && 'sticky left-0 z-10 bg-background font-medium',
                        col.key === 'methodology' && 'text-xs text-muted-foreground max-w-[240px] truncate',
                      )}
                      title={col.key === 'methodology' ? String(row.data[col.key] ?? '') : undefined}
                    >
                      {formatCellValue(row.data[col.key])}
                    </td>
                  ))}
                  {months.map((m) => {
                    const monthKey = monthToDataKey(m.month);
                    const isEditing =
                      editingCell?.rowId === row.id && editingCell?.monthKey === monthKey;
                    const cellValue = row.data[monthKey];

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
                              setEditingCell((prev) =>
                                prev ? { ...prev, value: e.target.value } : prev,
                              )
                            }
                            onBlur={() => handleCellSave(row)}
                            onKeyDown={(e) => handleCellKeyDown(e, row)}
                            autoFocus
                          />
                        ) : (
                          <span
                            className={cn(
                              isEditor && 'cursor-pointer hover:text-foreground',
                              !isEditor && 'text-muted-foreground',
                            )}
                          >
                            {formatCellValue(cellValue)}
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
                        onClick={() => handleDelete(row.id)}
                        disabled={deleteRow.isPending}
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
