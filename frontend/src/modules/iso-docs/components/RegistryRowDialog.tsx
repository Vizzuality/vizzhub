import { useState, useEffect, useRef } from 'react';
import { Paperclip, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
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
import { UserPicker } from './UserPicker';
import type { ColumnDef, RegistryRow, RegistryAttachment } from '../types/registry';

interface RegistryRowDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (v: boolean) => void;
  readonly columns: ColumnDef[];
  readonly row?: RegistryRow | null;
  readonly onSave: (data: Record<string, unknown>) => void;
  readonly isSaving: boolean;
  readonly onUploadAttachment?: (file: File) => void;
  readonly onDeleteAttachment?: (id: string) => void;
  readonly isUploading?: boolean;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function RegistryRowDialog({
  open,
  onOpenChange,
  columns,
  row,
  onSave,
  isSaving,
  onUploadAttachment,
  onDeleteAttachment,
  isUploading,
}: RegistryRowDialogProps): JSX.Element {
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setFormData(row?.data ?? {});
      setErrors({});
    }
  }, [open, row]);

  const setValue = (key: string, value: unknown): void => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const editableColumns = columns.filter((c) => c.type !== 'computed' && c.type !== 'attachment');

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    for (const col of editableColumns) {
      if (!col.required) continue;
      const val = formData[col.key];
      if (val === undefined || val === null || val === '') {
        newErrors[col.key] = 'Required';
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!validate()) return;
    onSave(formData);
  };

  const attachments: RegistryAttachment[] = row?.attachments ?? [];
  const submitLabel = (() => {
    if (isSaving) return 'Saving...';
    return row ? 'Save' : 'Add';
  })();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{row ? 'Edit Row' : 'Add Row'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {editableColumns.map((col) => (
              <div key={col.key} className="space-y-1.5">
                <Label htmlFor={`field-${col.key}`}>
                  {col.label}
                  {col.required && <span className="text-destructive ml-0.5">*</span>}
                </Label>
                {renderField(col)}
                {errors[col.key] && (
                  <p className="text-xs text-destructive">{errors[col.key]}</p>
                )}
              </div>
            ))}

            {row && onUploadAttachment && (
              <div className="space-y-2 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">Attachments</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                  >
                    <Paperclip className="h-3 w-3 mr-1" />
                    {isUploading ? 'Uploading...' : 'Attach file'}
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) onUploadAttachment(file);
                      e.target.value = '';
                    }}
                  />
                </div>
                {attachments.length > 0 && (
                  <div className="space-y-1">
                    {attachments.map((att) => (
                      <div
                        key={att.id}
                        className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" />
                          <span className="truncate">{att.filename}</span>
                          <span className="text-muted-foreground shrink-0">
                            {formatFileSize(att.size_bytes)}
                          </span>
                        </div>
                        {onDeleteAttachment && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0"
                            onClick={() => onDeleteAttachment(att.id)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );

  function renderField(col: ColumnDef): JSX.Element {
    const value = formData[col.key];

    switch (col.type) {
      case 'string':
        return (
          <Input
            id={`field-${col.key}`}
            value={(value as string) ?? ''}
            onChange={(e) => setValue(col.key, e.target.value)}
          />
        );
      case 'number':
        return (
          <Input
            id={`field-${col.key}`}
            type="number"
            value={value != null ? String(value) : ''}
            onChange={(e) => setValue(col.key, e.target.value ? Number(e.target.value) : null)}
          />
        );
      case 'date':
        return (
          <Input
            id={`field-${col.key}`}
            type="date"
            value={(value as string) ?? ''}
            onChange={(e) => setValue(col.key, e.target.value || null)}
          />
        );
      case 'boolean':
        return (
          <div className="flex items-center gap-2">
            <Switch
              id={`field-${col.key}`}
              checked={!!value}
              onCheckedChange={(v) => setValue(col.key, v)}
            />
            <span className="text-sm text-muted-foreground">
              {value ? 'Yes' : 'No'}
            </span>
          </div>
        );
      case 'select':
        return (
          <Select
            value={(value as string) ?? ''}
            onValueChange={(v) => setValue(col.key, v)}
          >
            <SelectTrigger id={`field-${col.key}`}>
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {(col.options ?? []).map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case 'user':
        return (
          <UserPicker
            value={(value as string) || null}
            onSelect={(v) => setValue(col.key, v)}
          />
        );
      default:
        return <Input value={String(value ?? '')} readOnly />;
    }
  }
}

