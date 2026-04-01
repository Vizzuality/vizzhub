import { Plus, Trash2, GripVertical } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import type { ColumnDef } from '../types/registry';

const COLUMN_TYPES = [
  { value: 'string', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'boolean', label: 'Yes/No' },
  { value: 'select', label: 'Dropdown' },
  { value: 'user', label: 'User' },
] as const;

function toKey(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .replace(/^(\d)/, '_$1');
}

interface RegistryColumnEditorProps {
  readonly columns: ColumnDef[];
  readonly onChange: (columns: ColumnDef[]) => void;
}

export function RegistryColumnEditor({ columns, onChange }: RegistryColumnEditorProps): JSX.Element {
  const addColumn = (): void => {
    onChange([
      ...columns,
      { key: '', label: '', type: 'string', required: false },
    ]);
  };

  const updateColumn = (index: number, updates: Partial<ColumnDef>): void => {
    const updated = columns.map((col, i) => {
      if (i !== index) return col;
      const merged = { ...col, ...updates };
      if (updates.label !== undefined && !col.key) {
        merged.key = toKey(updates.label);
      }
      if (merged.type !== 'select') {
        delete merged.options;
      }
      return merged;
    });
    onChange(updated);
  };

  const removeColumn = (index: number): void => {
    onChange(columns.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Columns</Label>
        <Button type="button" variant="outline" size="sm" onClick={addColumn}>
          <Plus className="h-3 w-3 mr-1" />
          Add column
        </Button>
      </div>

      {columns.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          Add at least one column to define the schema
        </p>
      )}

      <div className="space-y-2">
        {columns.map((col, index) => (
          <div
            key={index}
            className="flex items-start gap-2 p-3 rounded-md border bg-muted/30"
          >
            <GripVertical className="h-4 w-4 mt-2.5 text-muted-foreground shrink-0 cursor-grab" />
            <div className="flex-1 grid grid-cols-2 gap-2">
              <Input
                placeholder="Column label"
                value={col.label}
                onChange={(e) => updateColumn(index, { label: e.target.value, key: toKey(e.target.value) })}
              />
              <Select
                value={col.type}
                onValueChange={(v) => updateColumn(index, { type: v as ColumnDef['type'] })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COLUMN_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {col.type === 'select' && (
                <div className="col-span-2">
                  <Input
                    placeholder="Options (comma-separated)"
                    value={col.options?.join(', ') ?? ''}
                    onChange={(e) =>
                      updateColumn(index, {
                        options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      })
                    }
                  />
                </div>
              )}
              <div className="flex items-center gap-2 col-span-2">
                <Switch
                  checked={col.required}
                  onCheckedChange={(v) => updateColumn(index, { required: v })}
                  id={`required-${index}`}
                />
                <Label htmlFor={`required-${index}`} className="text-sm">
                  Required
                </Label>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 mt-0.5"
              onClick={() => removeColumn(index)}
            >
              <Trash2 className="h-4 w-4 text-muted-foreground" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
