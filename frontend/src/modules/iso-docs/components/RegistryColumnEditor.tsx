import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
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
  { value: 'attachment', label: 'Attachment' },
  { value: 'url', label: 'URL' },
] as const;

function toKey(label: string): string {
  return label
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, '_')
    .replaceAll(/^_|_$/g, '')
    .replace(/^(\d)/, '_$1');
}

interface SortableColumnProps {
  readonly id: string;
  readonly col: ColumnDef;
  readonly index: number;
  readonly onUpdate: (index: number, updates: Partial<ColumnDef>) => void;
  readonly onRemove: (index: number) => void;
}

function SortableColumn({ id, col, index, onUpdate, onRemove }: SortableColumnProps): JSX.Element {
  const [optionsText, setOptionsText] = useState(col.options?.join(', ') ?? '');

  const commitOptions = (): void => {
    const parsed = optionsText.split(',').map((s) => s.trim()).filter(Boolean);
    onUpdate(index, { options: parsed.length ? parsed : undefined });
  };

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-start gap-2 p-3 rounded-md border bg-muted/30"
    >
      <button
        type="button"
        className="mt-2.5 shrink-0 cursor-grab text-muted-foreground hover:text-foreground touch-none"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="flex-1 grid grid-cols-2 gap-2">
        <Input
          placeholder="Column label"
          value={col.label}
          onChange={(e) => onUpdate(index, { label: e.target.value })}
        />
        <Select
          value={col.type}
          onValueChange={(v) => onUpdate(index, { type: v as ColumnDef['type'] })}
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
              value={optionsText}
              onChange={(e) => setOptionsText(e.target.value)}
              onBlur={commitOptions}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitOptions(); } }}
            />
          </div>
        )}
        <div className="flex items-center gap-2 col-span-2">
          <Switch
            checked={col.required}
            onCheckedChange={(v) => onUpdate(index, { required: v })}
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
        onClick={() => onRemove(index)}
      >
        <Trash2 className="h-4 w-4 text-muted-foreground" />
      </Button>
    </div>
  );
}

interface RegistryColumnEditorProps {
  readonly columns: ColumnDef[];
  readonly onChange: (columns: ColumnDef[]) => void;
}

export function RegistryColumnEditor({ columns, onChange }: RegistryColumnEditorProps): JSX.Element {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const sortableIds = columns.map((_, i) => `col-${i}`);

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

  const handleDragEnd = (event: DragEndEvent): void => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = sortableIds.indexOf(active.id as string);
    const newIndex = sortableIds.indexOf(over.id as string);
    const reordered = [...columns];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);
    onChange(reordered);
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

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {columns.map((col, index) => (
              <SortableColumn
                key={sortableIds[index]}
                id={sortableIds[index]}
                col={col}
                index={index}
                onUpdate={updateColumn}
                onRemove={removeColumn}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
