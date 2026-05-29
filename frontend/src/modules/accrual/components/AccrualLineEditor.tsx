import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown, Loader2, Trash2, X } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/shared/components/ui/sheet';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { useAllProjectSummaries } from '@/core/hooks/useProjects';
import { useLineMutations } from '@/modules/accrual/hooks/useLineMutations';
import { useAccrualMutations } from '@/modules/accrual/hooks/useAccrualMutations';
import { accrualApi } from '@/modules/accrual/services/accrual';
import { queryKeys } from '@/core/hooks/queryKeys';
import type {
  AccrualLineCreate,
  AccrualLineProject,
  AccrualLineUpdate,
} from '@/modules/accrual/types/accrual';

interface LineForm {
  name: string;
  valueEur: string;
  valueOrig: string;
  currency: string;
  windowStart: string;
  windowEnd: string;
}

const EMPTY_FORM: LineForm = {
  name: '',
  valueEur: '0',
  valueOrig: '',
  currency: '',
  windowStart: '',
  windowEnd: '',
};

export interface AccrualLineEditorProps {
  /** Line id to edit, 'new' to create, or null when the editor is closed. */
  readonly lineId: string | null;
  readonly onClose: () => void;
}

interface ProjectPickerProps {
  readonly linkedIds: ReadonlySet<string>;
  readonly onPick: (projectId: string) => void;
}

function ProjectPicker({ linkedIds, onPick }: ProjectPickerProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const { data: projects = [] } = useAllProjectSummaries();
  const available = projects.filter((p) => !linkedIds.has(p.id));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="w-full justify-between font-normal">
          Link a project…
          <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search project…" />
          <CommandList>
            <CommandEmpty>No project found.</CommandEmpty>
            <CommandGroup>
              {available.map((p) => (
                <CommandItem
                  key={p.id}
                  value={`${p.code ?? ''} ${p.name}`}
                  onSelect={() => {
                    onPick(p.id);
                    setOpen(false);
                  }}
                >
                  <Check className="mr-2 h-4 w-4 opacity-0" />
                  <span className="truncate">
                    {p.code ? `${p.code} · ` : ''}
                    {p.name}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

function ProjectChips({
  projects,
  onRemove,
}: {
  readonly projects: AccrualLineProject[];
  readonly onRemove: (projectId: string) => void;
}): JSX.Element {
  if (projects.length === 0) {
    return <p className="text-xs italic text-muted-foreground">No linked projects (unlinked line).</p>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {projects.map((p) => (
        <li
          key={p.id}
          className="flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs"
          title={p.name}
        >
          <span className="max-w-[12rem] truncate">{p.code ?? p.name}</span>
          <button
            type="button"
            aria-label={`Unlink ${p.code ?? p.name}`}
            className="text-muted-foreground hover:text-destructive"
            onClick={() => onRemove(p.id)}
          >
            <X className="h-3 w-3" />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function AccrualLineEditor({ lineId, onClose }: AccrualLineEditorProps): JSX.Element {
  const isCreate = lineId === 'new';
  const editId = isCreate ? null : lineId;

  const { create, update, remove, linkProject, unlinkProject } = useLineMutations();
  const { redistributeLine } = useAccrualMutations();

  const { data: detail } = useQuery({
    queryKey: editId ? queryKeys.accrual.lines.detail(editId) : ['accrual', 'lines', 'none'],
    queryFn: () => accrualApi.lines.get(editId as string),
    enabled: Boolean(editId),
  });

  const [form, setForm] = useState<LineForm>(EMPTY_FORM);
  const [newProjects, setNewProjects] = useState<AccrualLineProject[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Seed the form: blank for create, fetched detail for edit.
  useEffect(() => {
    if (isCreate) {
      setForm(EMPTY_FORM);
      setNewProjects([]);
      return;
    }
    if (detail) {
      setForm({
        name: detail.name ?? '',
        valueEur: detail.value_eur ?? '0',
        valueOrig: detail.value_orig ?? '',
        currency: detail.currency ?? '',
        windowStart: detail.window_start ?? '',
        windowEnd: detail.window_end ?? '',
      });
    }
  }, [isCreate, detail]);

  const linkedProjects = useMemo<AccrualLineProject[]>(
    () => (isCreate ? newProjects : (detail?.projects ?? [])),
    [isCreate, newProjects, detail],
  );
  const linkedIds = useMemo(
    () => new Set(linkedProjects.map((p) => p.id)),
    [linkedProjects],
  );
  const allProjects = useAllProjectSummaries().data ?? [];

  const setField = (key: keyof LineForm, value: string): void =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const windowInvalid =
    Boolean(form.windowStart) &&
    Boolean(form.windowEnd) &&
    form.windowStart > form.windowEnd;

  const buildPayload = (): AccrualLineUpdate => ({
    name: form.name.trim() || null,
    value_eur: form.valueEur || '0',
    value_orig: form.valueOrig.trim() || null,
    currency: form.currency.trim().toUpperCase() || null,
    window_start: form.windowStart || null,
    window_end: form.windowEnd || null,
  });

  const handlePickProject = (projectId: string): void => {
    if (isCreate) {
      const proj = allProjects.find((p) => p.id === projectId);
      if (proj) {
        setNewProjects((prev) => [
          ...prev,
          {
            id: proj.id,
            code: proj.code ?? null,
            name: proj.name,
            status: '',
            project_manager_id: null,
            project_manager_name: null,
          },
        ]);
      }
    } else if (editId) {
      void linkProject.mutateAsync({ id: editId, projectId });
    }
  };

  const handleRemoveProject = (projectId: string): void => {
    if (isCreate) {
      setNewProjects((prev) => prev.filter((p) => p.id !== projectId));
    } else if (editId) {
      void unlinkProject.mutateAsync({ id: editId, projectId });
    }
  };

  const handleSave = async (): Promise<void> => {
    if (windowInvalid) return;
    if (isCreate) {
      const payload: AccrualLineCreate = {
        ...buildPayload(),
        value_eur: form.valueEur || '0',
        project_ids: newProjects.map((p) => p.id),
      };
      await create.mutateAsync(payload).then(onClose).catch(() => undefined);
    } else if (editId) {
      await update
        .mutateAsync({ id: editId, payload: buildPayload() })
        .then(onClose)
        .catch(() => undefined);
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!editId) return;
    await remove.mutateAsync(editId).catch(() => undefined);
    setConfirmDelete(false);
    onClose();
  };

  const saving = create.isPending || update.isPending;

  return (
    <Sheet open={lineId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="flex w-full flex-col gap-4 overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{isCreate ? 'New accrual line' : 'Edit accrual line'}</SheetTitle>
          <SheetDescription>
            A line is one revenue-recognition unit. Its window is independent of the
            tracker contract.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="line-name">Name</Label>
            <Input
              id="line-name"
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              placeholder="Line name"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="line-value-eur">Value €</Label>
              <Input
                id="line-value-eur"
                type="number"
                min="0"
                step="0.01"
                value={form.valueEur}
                onChange={(e) => setField('valueEur', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="line-value-orig">Original</Label>
              <Input
                id="line-value-orig"
                type="number"
                min="0"
                step="0.01"
                value={form.valueOrig}
                onChange={(e) => setField('valueOrig', e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="line-currency">Currency (ISO)</Label>
            <Input
              id="line-currency"
              value={form.currency}
              maxLength={3}
              onChange={(e) => setField('currency', e.target.value)}
              placeholder="EUR"
              className="uppercase"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="line-window-start">Window start</Label>
              <Input
                id="line-window-start"
                type="date"
                value={form.windowStart}
                onChange={(e) => setField('windowStart', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="line-window-end">Window end</Label>
              <Input
                id="line-window-end"
                type="date"
                value={form.windowEnd}
                onChange={(e) => setField('windowEnd', e.target.value)}
              />
            </div>
          </div>
          {windowInvalid && (
            <p className="text-xs text-destructive">Window start must be on or before end.</p>
          )}
        </div>

        <div className="space-y-2">
          <Label>Linked projects</Label>
          <ProjectChips projects={linkedProjects} onRemove={handleRemoveProject} />
          <ProjectPicker linkedIds={linkedIds} onPick={handlePickProject} />
        </div>

        {!isCreate && editId && (
          <div className="space-y-2 rounded-md border p-3">
            <Label>Redistribute</Label>
            <p className="text-xs text-muted-foreground">
              Spread <strong>Value €</strong> evenly across the window's mutable months
              (skips frozen cells and manual overrides).
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void redistributeLine(editId)}
            >
              Redistribute across window
            </Button>
          </div>
        )}

        <SheetFooter className="mt-auto flex-row items-center justify-between gap-2">
          {!isCreate && editId && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="mr-1 h-4 w-4" />
              Delete
            </Button>
          )}
          <div className="ml-auto flex gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="button" onClick={() => void handleSave()} disabled={saving || windowInvalid}>
              {saving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {isCreate ? 'Create line' : 'Save'}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this line?</AlertDialogTitle>
            <AlertDialogDescription>
              The line and all its cells are removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleDelete()}
              disabled={remove.isPending}
            >
              {remove.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sheet>
  );
}
