import { useState, useRef, useEffect, useCallback } from 'react';
import { Check, X, ExternalLink } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Switch } from '@/shared/components/ui/switch';
import { UserPicker } from './UserPicker';
import type { ColumnDef } from '../types/registry';

const URL_REGEX = /^https?:\/\//;

interface InlineCellProps {
  readonly value: unknown;
  readonly col: ColumnDef;
  readonly isEditor: boolean;
  readonly onSave: (key: string, value: unknown) => void;
}

function DisplayValue({ value, col }: { value: unknown; col: ColumnDef }): JSX.Element {
  if (value === null || value === undefined || value === '') {
    return <span className="text-muted-foreground">-</span>;
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
  return <>{str}</>;
}

export function InlineCell({ value, col, isEditor, onSave }: InlineCellProps): JSX.Element {
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
    if (draft !== value) {
      onSave(col.key, draft === '' ? null : draft);
    }
  }, [draft, value, col.key, onSave]);

  const cancel = useCallback(() => {
    setDraft(value);
    setEditing(false);
  }, [value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        commit();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        cancel();
      }
      e.stopPropagation();
    },
    [commit, cancel],
  );

  const startEditing = useCallback(
    (e: React.MouseEvent) => {
      if (!isEditor) return;
      e.stopPropagation();
      setDraft(value);
      setEditing(true);
    },
    [isEditor, value],
  );

  if (!editing) {
    return (
      <div
        role="textbox"
        tabIndex={0}
        className={`min-h-[1.5rem] flex items-center ${isEditor ? 'cursor-text' : ''}`}
        onDoubleClick={startEditing}
      >
        <DisplayValue value={value} col={col} />
      </div>
    );
  }

  switch (col.type) {
    case 'boolean':
      return (
        <Switch
          className="flex items-center"
          checked={!!draft}
          onCheckedChange={(v) => {
            setDraft(v);
            setEditing(false);
            onSave(col.key, v);
          }}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          autoFocus
        />
      );

    case 'select':
      return (
        <Select
          value={(draft as string) ?? ''}
          onValueChange={(v) => {
            setDraft(v);
            setEditing(false);
            onSave(col.key, v);
          }}
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
          value={(value as string) ?? null}
          defaultOpen
          onSelect={(name) => {
            setEditing(false);
            onSave(col.key, name);
          }}
          onCancel={cancel}
          triggerClassName="h-7 text-sm justify-between min-w-[140px]"
        />
      );

    case 'date':
      return (
        <Input
          ref={inputRef}
          type="date"
          className="h-7 text-sm w-36"
          value={(draft as string) ?? ''}
          onChange={(e) => setDraft(e.target.value || null)}
          onClick={(e) => e.stopPropagation()}
          onBlur={commit}
          onKeyDown={handleKeyDown}
        />
      );

    case 'number':
      return (
        <Input
          ref={inputRef}
          type="number"
          className="h-7 text-sm w-24"
          value={draft != null ? String(draft) : ''}
          onChange={(e) => setDraft(e.target.value ? Number(e.target.value) : null)}
          onClick={(e) => e.stopPropagation()}
          onBlur={commit}
          onKeyDown={handleKeyDown}
        />
      );

    default:
      return (
        <Input
          ref={inputRef}
          type="text"
          className="h-7 text-sm"
          value={(draft as string) ?? ''}
          onChange={(e) => setDraft(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          onBlur={commit}
          onKeyDown={handleKeyDown}
        />
      );
  }
}
