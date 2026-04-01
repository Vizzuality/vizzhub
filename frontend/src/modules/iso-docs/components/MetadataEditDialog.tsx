import { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
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
import { CLASSIFICATION_LABELS, STATUS_LABELS } from '../types/isoDocs';
import type { IsoDocMetadata, MetadataUpdate, ChangelogEntry } from '../types/isoDocs';

const CLASSIFICATIONS = Object.entries(CLASSIFICATION_LABELS).map(([value, label]) => ({ value, label }));
const STATUSES = Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface MetadataEditDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly metadata: IsoDocMetadata;
  readonly onSave: (data: MetadataUpdate) => void;
  readonly isSaving: boolean;
}

function TagInput({
  label,
  values,
  onChange,
  placeholder,
}: Readonly<{
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
}>): JSX.Element {
  const [inputValue, setInputValue] = useState('');

  const handleAdd = (): void => {
    const trimmed = inputValue.trim();
    if (trimmed && !values.includes(trimmed)) {
      onChange([...values, trimmed]);
      setInputValue('');
    }
  };

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <div className="flex gap-1.5">
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAdd(); } }}
          placeholder={placeholder}
          className="h-8 text-sm"
        />
        <Button type="button" variant="outline" size="sm" className="h-8 px-2" onClick={handleAdd}>
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {values.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-xs font-mono"
            >
              {v}
              <button
                className="ml-0.5 hover:text-destructive"
                onClick={() => onChange(values.filter((x) => x !== v))}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ChangelogEditor({
  entries,
  onChange,
}: Readonly<{
  entries: ChangelogEntry[];
  onChange: (entries: ChangelogEntry[]) => void;
}>): JSX.Element {
  const handleEntryChange = (index: number, field: keyof ChangelogEntry, value: string): void => {
    const updated = entries.map((e, i) => (i === index ? { ...e, [field]: value } : e));
    onChange(updated);
  };

  const handleAdd = (): void => {
    onChange([{ version: '', date: new Date().toISOString().split('T')[0], author: '', description: '' }, ...entries]);
  };

  const handleRemove = (index: number): void => {
    onChange(entries.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Changelog</Label>
        <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={handleAdd}>
          <Plus className="h-3 w-3 mr-1" /> Add entry
        </Button>
      </div>
      {entries.map((entry, i) => (
        <div key={`${entry.version}-${entry.date}-${i}`} className="grid grid-cols-[1fr_1fr_1fr_2fr_auto] gap-1.5 items-start">
          <Input
            value={entry.version}
            onChange={(e) => handleEntryChange(i, 'version', e.target.value)}
            placeholder="Version"
            className="h-7 text-xs"
          />
          <Input
            value={entry.date}
            onChange={(e) => handleEntryChange(i, 'date', e.target.value)}
            placeholder="Date"
            className="h-7 text-xs"
          />
          <Input
            value={entry.author}
            onChange={(e) => handleEntryChange(i, 'author', e.target.value)}
            placeholder="Author"
            className="h-7 text-xs"
          />
          <Input
            value={entry.description}
            onChange={(e) => handleEntryChange(i, 'description', e.target.value)}
            placeholder="Description"
            className="h-7 text-xs"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => handleRemove(i)}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      ))}
    </div>
  );
}

export function MetadataEditDialog({
  open,
  onOpenChange,
  metadata,
  onSave,
  isSaving,
}: MetadataEditDialogProps): JSX.Element {
  const [form, setForm] = useState<MetadataUpdate>({});

  useEffect(() => {
    if (open) {
      setForm({
        code: metadata.code ?? '',
        standard: metadata.standard ?? [],
        clauses: metadata.clauses ?? [],
        classification: metadata.classification ?? 'internal_use',
        doc_version: metadata.doc_version ?? '',
        status: metadata.status ?? '',
        changelog: metadata.changelog?.map((e) => ({ ...e })) ?? [],
      });
    }
  }, [open, metadata]);

  const handleSave = (): void => {
    const data: MetadataUpdate = {
      code: form.code || null,
      standard: form.standard?.length ? form.standard : null,
      clauses: form.clauses?.length ? form.clauses : null,
      classification: form.classification || 'internal_use',
      doc_version: form.doc_version || null,
      status: form.status || null,
      changelog: form.changelog?.length ? form.changelog : null,
    };
    onSave(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Metadata</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Document Code</Label>
              <Input
                value={form.code ?? ''}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="e.g. PO01"
                className="h-8 text-sm font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Version</Label>
              <Input
                value={form.doc_version ?? ''}
                onChange={(e) => setForm({ ...form, doc_version: e.target.value })}
                placeholder="e.g. 2.0"
                className="h-8 text-sm font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select
                value={form.status ?? ''}
                onValueChange={(v) => setForm({ ...form, status: v })}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Classification</Label>
              <Select
                value={form.classification ?? 'internal_use'}
                onValueChange={(v) => setForm({ ...form, classification: v })}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select classification" />
                </SelectTrigger>
                <SelectContent>
                  {CLASSIFICATIONS.map((c) => (
                    <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <TagInput
            label="Standards"
            values={form.standard ?? []}
            onChange={(v) => setForm({ ...form, standard: v })}
            placeholder="e.g. ISO 27001:2022"
          />

          <TagInput
            label="Clauses"
            values={form.clauses ?? []}
            onChange={(v) => setForm({ ...form, clauses: v })}
            placeholder="e.g. 5.2"
          />

          <ChangelogEditor
            entries={form.changelog ?? []}
            onChange={(v) => setForm({ ...form, changelog: v })}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
