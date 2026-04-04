import { useState, useRef, useEffect, useCallback } from 'react';
import { Check, X, ExternalLink, Upload, Trash2, FileText, Image } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import { UserPicker } from './UserPicker';
import type { ColumnDef, RegistryAttachment } from '../types/registry';

const URL_REGEX = /^https?:\/\//;

interface InlineCellProps {
  readonly value: unknown;
  readonly col: ColumnDef;
  readonly isEditor: boolean;
  readonly onSave: (key: string, value: unknown) => void;
  readonly attachment?: RegistryAttachment;
  readonly onUploadAttachment?: (fieldKey: string, file: File) => void;
  readonly onDeleteAttachment?: (attachmentId: string) => void;
}

function getConditionalColor(
  value: unknown,
  ranges?: { min: number; max: number; color: string; label?: string }[],
): { color: string; label?: string } | null {
  if (!ranges || value === null || value === undefined) return null;
  const num = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(num)) return null;
  return ranges.find((r) => num >= r.min && num <= r.max) ?? null;
}

function DisplayValue({ value, col }: { value: unknown; col: ColumnDef }): JSX.Element {
  if (value === null || value === undefined || value === '') {
    return <span className="text-muted-foreground">-</span>;
  }
  if (col.type === 'computed') {
    const match = getConditionalColor(value, col.conditional_format);
    if (match) {
      return (
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold"
          style={{ backgroundColor: match.color, color: '#fff' }}
        >
          {String(value)}
          {match.label && <span className="font-normal">({match.label})</span>}
        </span>
      );
    }
    return <span className="font-medium">{String(value)}</span>;
  }
  if (col.type === 'select' && col.option_colors) {
    const str = String(value);
    const color = col.option_colors[str];
    if (color) {
      return (
        <span
          className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold"
          style={{ backgroundColor: color, color: '#fff' }}
        >
          {str}
        </span>
      );
    }
    return <span className="block truncate">{str}</span>;
  }
  if (col.type === 'boolean') {
    return value ? (
      <Check className="h-4 w-4 text-green-600" />
    ) : (
      <X className="h-4 w-4 text-muted-foreground" />
    );
  }
  const str = String(value);
  if (URL_REGEX.test(str)) {
    return (
      <a
        href={str}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline inline-flex items-center gap-1"
        onClick={(e) => e.stopPropagation()}
      >
        <ExternalLink className="h-3 w-3 shrink-0" />
        Link
      </a>
    );
  }
  return <span className="block truncate">{str}</span>;
}

function AttachmentIcon({ contentType }: { readonly contentType: string }): JSX.Element {
  if (contentType.startsWith('image/')) return <Image className="h-3.5 w-3.5 shrink-0" />;
  return <FileText className="h-3.5 w-3.5 shrink-0" />;
}

function AttachmentCell({
  col, attachment, isEditor, onUploadAttachment, onDeleteAttachment,
}: {
  readonly col: ColumnDef;
  readonly attachment?: RegistryAttachment;
  readonly isEditor: boolean;
  readonly onUploadAttachment?: (fieldKey: string, file: File) => void;
  readonly onDeleteAttachment?: (attachmentId: string) => void;
}): JSX.Element {
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (attachment) {
    return (
      <div className="flex items-center gap-1 min-h-[1.5rem]">
        <a
          href={attachment.url ?? '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline inline-flex items-center gap-1 text-sm truncate"
          title={attachment.filename}
          onClick={(e) => e.stopPropagation()}
        >
          <AttachmentIcon contentType={attachment.content_type} />
          <span className="truncate max-w-[150px]">{attachment.filename}</span>
        </a>
        {isEditor && onDeleteAttachment && (
          <button
            type="button"
            className="text-muted-foreground hover:text-destructive shrink-0"
            onClick={(e) => { e.stopPropagation(); onDeleteAttachment(attachment.id); }}
            title="Remove attachment"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  if (!isEditor || !onUploadAttachment) {
    return <div className="flex items-center min-h-[1.5rem]"><span className="text-muted-foreground">-</span></div>;
  }

  return (
    <div className="flex items-center min-h-[1.5rem]">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUploadAttachment(col.key, file);
          e.target.value = '';
        }}
      />
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
        title="Upload file"
      >
        <Upload className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

interface EditingFieldProps {
  readonly col: ColumnDef;
  readonly value: unknown;
  readonly draft: unknown;
  readonly inputRef: React.RefObject<HTMLInputElement>;
  readonly setDraft: (v: unknown) => void;
  readonly commit: () => void;
  readonly cancel: () => void;
  readonly handleKeyDown: (e: React.KeyboardEvent) => void;
  readonly setEditing: (v: boolean) => void;
  readonly onSave: (key: string, value: unknown) => void;
}

function EditingField({
  col, value, draft, inputRef, setDraft, commit, cancel, handleKeyDown, setEditing, onSave,
}: EditingFieldProps): JSX.Element {
  switch (col.type) {
    case 'boolean':
      return (
        <Switch
          className="flex items-center"
          checked={!!draft}
          onCheckedChange={(v) => { setDraft(v); setEditing(false); onSave(col.key, v); }}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          autoFocus
        />
      );

    case 'select':
      return (
        <Select
          value={(draft as string) ?? ''}
          onValueChange={(v) => { setDraft(v); setEditing(false); onSave(col.key, v); }}
          open
          onOpenChange={(open) => { if (!open) cancel(); }}
        >
          <SelectTrigger
            className="h-7 text-sm min-w-[100px]"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <SelectValue placeholder="Select..." />
          </SelectTrigger>
          <SelectContent>
            {(col.options ?? []).map((opt) => (
              <SelectItem key={opt} value={opt}>{opt}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      );

    case 'user':
      return (
        <UserPicker
          value={(value as string) ?? null}
          defaultOpen
          onSelect={(name) => { setEditing(false); onSave(col.key, name); }}
          onCancel={cancel}
          triggerClassName="h-7 text-sm justify-between min-w-[140px]"
        />
      );

    case 'date':
      return (
        <Input ref={inputRef} type="date" className="h-7 text-sm w-36"
          value={(draft as string) ?? ''} onChange={(e) => setDraft(e.target.value || null)}
          onClick={(e) => e.stopPropagation()} onBlur={commit} onKeyDown={handleKeyDown} />
      );

    case 'number':
      return (
        <Input ref={inputRef} type="number" className="h-7 text-sm w-24"
          value={draft != null ? String(draft) : ''}
          onChange={(e) => setDraft(e.target.value ? Number(e.target.value) : null)}
          onClick={(e) => e.stopPropagation()} onBlur={commit} onKeyDown={handleKeyDown} />
      );

    default: {
      const strVal = (draft as string) ?? '';
      if (strVal.length > 80 || strVal.includes('\n')) {
        return (
          <Textarea autoFocus className="text-sm min-h-[5rem]" value={strVal}
            onChange={(e) => setDraft(e.target.value)} onClick={(e) => e.stopPropagation()}
            onBlur={commit} onKeyDown={(e) => {
              if (e.key === 'Escape') { e.preventDefault(); cancel(); }
              e.stopPropagation();
            }} />
        );
      }
      return (
        <Input ref={inputRef} type="text" className="h-7 text-sm" value={strVal}
          onChange={(e) => setDraft(e.target.value)} onClick={(e) => e.stopPropagation()}
          onBlur={commit} onKeyDown={handleKeyDown} />
      );
    }
  }
}

export function InlineCell({
  value, col, isEditor, onSave, attachment, onUploadAttachment, onDeleteAttachment,
}: InlineCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<unknown>(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const commit = useCallback(() => {
    setEditing(false);
    if (draft !== value) onSave(col.key, draft === '' ? null : draft);
  }, [draft, value, col.key, onSave]);

  const cancel = useCallback(() => { setDraft(value); setEditing(false); }, [value]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    else if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    e.stopPropagation();
  }, [commit, cancel]);

  const startEditing = useCallback((e: React.MouseEvent) => {
    if (!isEditor) return;
    e.stopPropagation();
    setDraft(value);
    setEditing(true);
  }, [isEditor, value]);

  if (col.type === 'attachment') {
    return <AttachmentCell col={col} attachment={attachment} isEditor={isEditor}
      onUploadAttachment={onUploadAttachment} onDeleteAttachment={onDeleteAttachment} />;
  }

  if (!editing || col.type === 'computed') {
    const editable = isEditor && col.type !== 'computed';
    return (
      <button
        type="button"
        className={`min-h-[1.5rem] flex items-center bg-transparent border-0 p-0 text-left text-inherit font-inherit w-full overflow-hidden ${editable ? 'cursor-text' : ''}`}
        onDoubleClick={editable ? startEditing : undefined}
        onKeyDown={editable ? (e) => { if (e.key === 'Enter') startEditing(e as unknown as React.MouseEvent); } : undefined}
      >
        <DisplayValue value={value} col={col} />
      </button>
    );
  }

  return <EditingField col={col} value={value} draft={draft} inputRef={inputRef}
    setDraft={setDraft} commit={commit} cancel={cancel} handleKeyDown={handleKeyDown}
    setEditing={setEditing} onSave={onSave} />;
}
