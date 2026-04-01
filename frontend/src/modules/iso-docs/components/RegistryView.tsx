import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { Plus, Download, Upload, Settings, Trash2, ChevronLeft, ChevronRight, Paperclip, ArrowUp, ArrowDown, Columns3, CheckCircle2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { InlineCell } from './InlineCell';
import { RegistryRowDialog } from './RegistryRowDialog';
import { RegistryTypeDialog } from './RegistryTypeDialog';
import { useRegistryType, useUpdateRegistryType } from '../hooks/useRegistryTypes';
import {
  useRegistryRows,
  useCreateRegistryRow,
  useUpdateRegistryRow,
  useDeleteRegistryRow,
  useExportRegistry,
  useExportToDrive,
  useImportCsv,
} from '../hooks/useRegistryRows';
import { useDriveExportStatus } from '../hooks/useDriveExport';
import { useUploadAttachment, useDeleteAttachment } from '../hooks/useRegistryAttachments';
import type { RegistryRow, ColumnDef } from '../types/registry';

interface RegistryViewProps {
  readonly nodeId: string;
  readonly registryTypeId: string;
  readonly isEditor: boolean;
}

const CURRENT_YEAR = new Date().getFullYear();

function generateYearOptions(): number[] {
  const years: number[] = [];
  for (let y = CURRENT_YEAR + 1; y >= CURRENT_YEAR - 10; y--) {
    years.push(y);
  }
  return years;
}

type SortDir = 'asc' | 'desc';

function compareValues(a: unknown, b: unknown, dir: SortDir): number {
  const aNull = a === null || a === undefined || a === '';
  const bNull = b === null || b === undefined || b === '';
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  const aStr = String(a);
  const bStr = String(b);

  const aNum = Number(a);
  const bNum = Number(b);
  if (!isNaN(aNum) && !isNaN(bNum)) {
    return dir === 'asc' ? aNum - bNum : bNum - aNum;
  }

  const cmp = aStr.localeCompare(bStr, undefined, { sensitivity: 'base' });
  return dir === 'asc' ? cmp : -cmp;
}

export function RegistryView({ nodeId, registryTypeId, isEditor }: RegistryViewProps): JSX.Element {
  const { data: registryType } = useRegistryType(registryTypeId);
  const [selectedYear, setSelectedYear] = useState<number>(CURRENT_YEAR);
  const [rowDialogOpen, setRowDialogOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<RegistryRow | null>(null);
  const [deleteRowId, setDeleteRowId] = useState<string | null>(null);
  const [typeDialogOpen, setTypeDialogOpen] = useState(false);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!feedback) return;
    const t = setTimeout(() => setFeedback(null), 3000);
    return () => clearTimeout(t);
  }, [feedback]);

  const isYearly = registryType?.is_yearly ?? false;
  const year = isYearly ? selectedYear : undefined;

  const { data: rows = [], isLoading } = useRegistryRows(nodeId, year);
  const createRow = useCreateRegistryRow(nodeId);
  const updateRow = useUpdateRegistryRow(nodeId);
  const deleteRow = useDeleteRegistryRow(nodeId);
  const exportRegistry = useExportRegistry(nodeId);
  const exportToDrive = useExportToDrive(nodeId);
  const importCsv = useImportCsv(nodeId);
  const { data: driveStatus } = useDriveExportStatus(isEditor);
  const updateType = useUpdateRegistryType();
  const uploadAttachment = useUploadAttachment(nodeId);
  const deleteAttachment = useDeleteAttachment(nodeId);
  const csvInputRef = useRef<HTMLInputElement>(null);
  const driveConnected = driveStatus?.connected ?? false;

  const allColumns: ColumnDef[] = registryType?.schema ?? [];
  const visibleColumns = useMemo(
    () => allColumns.filter((col) => !hiddenColumns.has(col.key)),
    [allColumns, hiddenColumns],
  );

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) =>
      compareValues(a.data[sortKey], b.data[sortKey], sortDir),
    );
  }, [rows, sortKey, sortDir]);

  const handleSort = useCallback((key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }, [sortKey]);

  const toggleColumn = useCallback((key: string) => {
    setHiddenColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const handleInlineSave = useCallback(
    (row: RegistryRow, key: string, value: unknown) => {
      const merged = { ...row.data, [key]: value };
      updateRow.mutate({ rowId: row.id, data: { data: merged } });
    },
    [updateRow],
  );

  const handleAddRow = useCallback(() => {
    setEditingRow(null);
    setRowDialogOpen(true);
  }, []);

  const handleOpenRowDialog = useCallback((row: RegistryRow) => {
    setEditingRow(row);
    setRowDialogOpen(true);
  }, []);

  const handleSaveRow = useCallback(
    (data: Record<string, unknown>) => {
      if (editingRow) {
        updateRow.mutate(
          { rowId: editingRow.id, data: { data } },
          { onSuccess: () => setRowDialogOpen(false) },
        );
      } else {
        createRow.mutate(
          { data, year: isYearly ? selectedYear : undefined },
          { onSuccess: () => setRowDialogOpen(false) },
        );
      }
    },
    [editingRow, updateRow, createRow, isYearly, selectedYear],
  );

  const handleDeleteRow = useCallback(() => {
    if (!deleteRowId) return;
    deleteRow.mutate(deleteRowId, {
      onSuccess: () => setDeleteRowId(null),
    });
  }, [deleteRowId, deleteRow]);

  const handleExport = useCallback((format: 'xlsx' | 'csv') => {
    exportRegistry.mutate({ format, year });
  }, [exportRegistry, year]);

  const handleExportToDrive = useCallback(() => {
    exportToDrive.mutate(year, {
      onSuccess: () => setFeedback('Exported to Google Drive'),
      onError: () => setFeedback('Export to Drive failed'),
    });
  }, [exportToDrive, year]);

  const handleImportCsv = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    importCsv.mutate({ file, year }, {
      onSuccess: (data) => setFeedback(`Imported ${data.imported} rows`),
      onError: () => setFeedback('CSV import failed'),
    });
    e.target.value = '';
  }, [importCsv, year]);

  const handleSaveType = useCallback(
    (data: { name: string; description: string | null; is_yearly: boolean; schema: ColumnDef[] }) => {
      if (!registryType) return;
      updateType.mutate(
        { id: registryType.id, data },
        { onSuccess: () => setTypeDialogOpen(false) },
      );
    },
    [registryType, updateType],
  );

  if (!registryType) {
    return <p className="text-sm text-muted-foreground">Loading registry...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3">
          {isYearly && (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => setSelectedYear((y) => y - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Select
                value={String(selectedYear)}
                onValueChange={(v) => setSelectedYear(Number(v))}
              >
                <SelectTrigger className="w-24 h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {generateYearOptions().map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => setSelectedYear((y) => y + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
          <span className="text-sm text-muted-foreground">
            {rows.length} {rows.length === 1 ? 'row' : 'rows'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Columns3 className="h-4 w-4 mr-1" />
                Columns
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-h-64 overflow-y-auto">
              {allColumns.map((col) => (
                <DropdownMenuCheckboxItem
                  key={col.key}
                  checked={!hiddenColumns.has(col.key)}
                  onCheckedChange={() => toggleColumn(col.key)}
                >
                  {col.label}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={exportRegistry.isPending}>
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport('xlsx')}>
                Export as XLSX
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('csv')}>
                Export as CSV
              </DropdownMenuItem>
              {driveConnected && (
                <DropdownMenuItem
                  onClick={handleExportToDrive}
                  disabled={exportToDrive.isPending}
                >
                  {exportToDrive.isPending ? 'Exporting...' : 'Export to Google Drive'}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          {isEditor && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => csvInputRef.current?.click()}
                disabled={importCsv.isPending}
              >
                <Upload className="h-4 w-4 mr-1" />
                {importCsv.isPending ? 'Importing...' : 'Import CSV'}
              </Button>
              <input
                ref={csvInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleImportCsv}
              />
              <Button variant="outline" size="sm" onClick={() => setTypeDialogOpen(true)}>
                <Settings className="h-4 w-4 mr-1" />
                Schema
              </Button>
              <Button size="sm" onClick={handleAddRow}>
                <Plus className="h-4 w-4 mr-1" />
                Add row
              </Button>
            </>
          )}
          {feedback && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {feedback}
            </span>
          )}
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : rows.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-sm">No data yet</p>
          {isEditor && (
            <Button variant="outline" size="sm" className="mt-3" onClick={handleAddRow}>
              <Plus className="h-4 w-4 mr-1" />
              Add first row
            </Button>
          )}
        </div>
      ) : (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left px-3 py-2 font-medium text-muted-foreground w-10">#</th>
                {visibleColumns.map((col) => (
                  <th
                    key={col.key}
                    className="text-left px-3 py-2 font-medium text-muted-foreground whitespace-nowrap cursor-pointer select-none hover:text-foreground transition-colors"
                    style={col.width ? { minWidth: col.width } : undefined}
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortKey === col.key && (
                        sortDir === 'asc'
                          ? <ArrowUp className="h-3 w-3" />
                          : <ArrowDown className="h-3 w-3" />
                      )}
                    </span>
                  </th>
                ))}
                {isEditor && (
                  <th className="text-right px-3 py-2 w-10" />
                )}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row, idx) => (
                <tr
                  key={row.id}
                  className="border-b last:border-b-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-1.5 text-muted-foreground">{idx + 1}</td>
                  {visibleColumns.map((col) => (
                    <td key={col.key} className="px-3 py-1.5 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <InlineCell
                          value={row.data[col.key]}
                          col={col}
                          isEditor={isEditor}
                          onSave={(key, value) => handleInlineSave(row, key, value)}
                        />
                        {row.attachments.some((a) => a.field_key === col.key) && (
                          <Paperclip className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                    </td>
                  ))}
                  {isEditor && (
                    <td className="px-3 py-1.5 text-right">
                      <div className="flex items-center justify-end gap-0.5">
                        {row.attachments.length > 0 && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => handleOpenRowDialog(row)}
                            title="Attachments"
                          >
                            <Paperclip className="h-3.5 w-3.5 text-muted-foreground" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => setDeleteRowId(row.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <RegistryRowDialog
        open={rowDialogOpen}
        onOpenChange={setRowDialogOpen}
        columns={allColumns}
        row={editingRow}
        onSave={handleSaveRow}
        isSaving={createRow.isPending}
        onUploadAttachment={
          editingRow
            ? (file) => uploadAttachment.mutate({ rowId: editingRow.id, file })
            : undefined
        }
        onDeleteAttachment={
          editingRow
            ? (id) => deleteAttachment.mutate(id)
            : undefined
        }
        isUploading={uploadAttachment.isPending}
      />

      <RegistryTypeDialog
        open={typeDialogOpen}
        onOpenChange={setTypeDialogOpen}
        registryType={registryType}
        onSave={handleSaveType}
        isSaving={updateType.isPending}
      />

      <AlertDialog open={!!deleteRowId} onOpenChange={(v) => !v && setDeleteRowId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete row?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this row and its attachments.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                handleDeleteRow();
              }}
            >
              {deleteRow.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
