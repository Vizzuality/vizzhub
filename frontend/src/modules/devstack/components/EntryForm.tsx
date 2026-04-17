import { useState, useEffect } from 'react';
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
import { Textarea } from '@/shared/components/ui/textarea';
import { Switch } from '@/shared/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  useDevstackEntry,
  useCreateDevstackEntry,
  useUpdateDevstackEntry,
} from '../hooks/useDevstack';
import {
  ENTRY_TYPES,
  INSTALL_METHODS,
  ENTRY_ORIGINS,
  type DevstackEntryCreate,
  type EntryType,
  type InstallMethod,
  type EntryOrigin,
} from '../types/devstack';

interface EntryFormProps {
  readonly selectedId: string | null;
  readonly onClose: () => void;
}

interface FormState {
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url: string;
  package: string;
  package_version: string;
  origin: EntryOrigin;
  tech: string;
  required: boolean;
  active: boolean;
}

const INITIAL_FORM: FormState = {
  name: '',
  description: '',
  type: 'skill',
  install_method: 'github',
  url: '',
  package: '',
  package_version: '',
  origin: 'internal',
  tech: '',
  required: false,
  active: true,
};

export function EntryForm({ selectedId, onClose }: EntryFormProps): JSX.Element {
  const isNew = selectedId === 'new';
  const editId = isNew ? '' : (selectedId ?? '');

  const { data: existing, isLoading } = useDevstackEntry(editId);
  const createEntry = useCreateDevstackEntry();
  const updateEntry = useUpdateDevstackEntry();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing && !isNew) {
      setForm({
        name: existing.name,
        description: existing.description,
        type: existing.type,
        install_method: existing.install_method,
        url: existing.url ?? '',
        package: existing.package ?? '',
        package_version: existing.package_version ?? '',
        origin: existing.origin,
        tech: existing.tech.join(', '),
        required: existing.required,
        active: existing.active,
      });
    }
  }, [existing, isNew]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]): void => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);

    if (!form.name.trim()) {
      setError('Name is required.');
      return;
    }

    const payload: DevstackEntryCreate = {
      name: form.name.trim(),
      description: form.description.trim(),
      type: form.type,
      install_method: form.install_method,
      url: form.install_method === 'github' && form.url ? form.url.trim() : null,
      package: form.install_method === 'npm' && form.package ? form.package.trim() : null,
      package_version:
        form.install_method === 'npm' && form.package_version
          ? form.package_version.trim()
          : null,
      origin: form.origin,
      tech: form.tech
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      required: form.required,
      active: form.active,
    };

    const onError = (err: unknown): void => {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setError(detail ?? 'Something went wrong.');
    };

    if (isNew) {
      createEntry.mutate(payload, { onSuccess: onClose, onError });
    } else {
      updateEntry.mutate({ id: editId, data: payload }, { onSuccess: onClose, onError });
    }
  };

  const isPending = createEntry.isPending || updateEntry.isPending;

  function submitLabel(): string {
    if (isPending) return 'Saving...';
    return isNew ? 'Create' : 'Save';
  }

  return (
    <Dialog open={selectedId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isNew ? 'New Entry' : 'Edit Entry'}</DialogTitle>
        </DialogHeader>

        {!isNew && isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="entry-name">Name *</Label>
              <Input
                id="entry-name"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                placeholder="Entry name"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="entry-desc">Description</Label>
              <Textarea
                id="entry-desc"
                rows={2}
                value={form.description}
                onChange={(e) => setField('description', e.target.value)}
                placeholder="What does this entry provide?"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select
                  value={form.type}
                  onValueChange={(v) => setField('type', v as EntryType)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ENTRY_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Install Method</Label>
                <Select
                  value={form.install_method}
                  onValueChange={(v) => setField('install_method', v as InstallMethod)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {INSTALL_METHODS.map((m) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {form.install_method === 'github' && (
              <div className="space-y-1.5">
                <Label htmlFor="entry-url">URL</Label>
                <Input
                  id="entry-url"
                  type="url"
                  value={form.url}
                  onChange={(e) => setField('url', e.target.value)}
                  placeholder="https://github.com/..."
                />
              </div>
            )}

            {form.install_method === 'npm' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="entry-pkg">Package</Label>
                  <Input
                    id="entry-pkg"
                    value={form.package}
                    onChange={(e) => setField('package', e.target.value)}
                    placeholder="@scope/package-name"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="entry-pkg-ver">Version</Label>
                  <Input
                    id="entry-pkg-ver"
                    value={form.package_version}
                    onChange={(e) => setField('package_version', e.target.value)}
                    placeholder="1.0.0"
                  />
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Origin</Label>
              <Select
                value={form.origin}
                onValueChange={(v) => setField('origin', v as EntryOrigin)}
              >
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTRY_ORIGINS.map((o) => (
                    <SelectItem key={o} value={o}>{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="entry-tech">Tech Tags (comma-separated)</Label>
              <Input
                id="entry-tech"
                value={form.tech}
                onChange={(e) => setField('tech', e.target.value)}
                placeholder="python, typescript, react"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-3">
                <Switch
                  id="entry-required"
                  checked={form.required}
                  onCheckedChange={(v) => setField('required', v)}
                />
                <Label htmlFor="entry-required">Required</Label>
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  id="entry-active"
                  checked={form.active}
                  onCheckedChange={(v) => setField('active', v)}
                />
                <Label htmlFor="entry-active">Active</Label>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                {submitLabel()}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
