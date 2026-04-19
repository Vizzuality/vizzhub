import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
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
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import {
  useCreateProjectContext,
  useUpdateProjectContext,
} from '../hooks/useProjectContexts';
import type { ProjectContext } from '../types/projectContexts';

interface ProjectContextFormProps {
  readonly context: ProjectContext | null;
  readonly onClose: () => void;
}

const SLUG_REGEX = /^[a-z0-9-]+$/;

function submitLabel(isPending: boolean, isEdit: boolean): string {
  if (isPending) return 'Saving...';
  return isEdit ? 'Save' : 'Create';
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function ProjectContextForm({
  context,
  onClose,
}: ProjectContextFormProps): JSX.Element {
  const isEdit = context !== null;
  const { data: projects = [] } = useActiveProjectSummaries();
  const createMutation = useCreateProjectContext();
  const updateMutation = useUpdateProjectContext();

  const [projectId, setProjectId] = useState(context?.project_id ?? '');
  const [slug, setSlug] = useState(context?.slug ?? '');
  const [description, setDescription] = useState(context?.description ?? '');
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);

  const selectedProjectName = isEdit
    ? (context.project_name ?? '')
    : (projects.find((p) => p.id === projectId)?.name ?? '');

  const handleProjectSelect = (id: string): void => {
    setProjectId(id);
    setProjectPickerOpen(false);
    if (!isEdit) {
      const project = projects.find((p) => p.id === id);
      if (project) setSlug(slugify(project.name));
    }
  };

  const handleSubmit = (): void => {
    setError(null);
    if (!isEdit && !SLUG_REGEX.test(slug)) {
      setError('Slug must contain only lowercase letters, digits, hyphens.');
      return;
    }

    if (isEdit && context) {
      updateMutation.mutate(
        { id: context.id, data: { description: description || null } },
        { onSuccess: onClose },
      );
    } else {
      createMutation.mutate(
        {
          slug,
          project_id: projectId,
          description: description || null,
        },
        {
          onSuccess: (created) => {
            // If the GitHub seed failed, keep the dialog open so the admin
            // reads the warning. The DB mapping is already saved — closing
            // via "Close" keeps it.
            if (created.github_error) {
              setWarning(created.github_error);
            } else {
              onClose();
            }
          },
        },
      );
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;
  const canSubmit = isEdit ? true : Boolean(projectId && slug);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit project context' : 'New project context'}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="project">Project</Label>
            <Popover
              open={projectPickerOpen}
              onOpenChange={setProjectPickerOpen}
            >
              <PopoverTrigger asChild>
                <Button
                  id="project"
                  role="combobox"
                  aria-expanded={projectPickerOpen}
                  variant="outline"
                  disabled={isEdit}
                  className="w-full justify-between font-normal"
                >
                  {selectedProjectName || 'Select a project...'}
                  <ChevronsUpDown className="h-4 w-4 ml-2 opacity-50 shrink-0" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                className="w-[--radix-popover-trigger-width] p-0"
                align="start"
              >
                <Command>
                  <CommandInput placeholder="Search project..." />
                  <CommandList>
                    <CommandEmpty>No project found.</CommandEmpty>
                    <CommandGroup>
                      {projects.map((p) => (
                        <CommandItem
                          key={p.id}
                          value={p.name}
                          onSelect={() => handleProjectSelect(p.id)}
                        >
                          <Check
                            className={`h-4 w-4 mr-2 ${projectId === p.id ? 'opacity-100' : 'opacity-0'}`}
                          />
                          {p.name}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          <div className="space-y-2">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={isEdit}
              placeholder="acme-corp"
            />
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                Slug is immutable after creation. Delete and recreate to rename.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          {warning && (
            <div className="rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
              <p className="font-medium">Mapping saved, but GitHub seed failed</p>
              <p className="mt-1 text-xs">{warning}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                The project context is registered in VizzHub. Create{' '}
                <code className="font-mono">{slug}/CLAUDE.md</code> manually in
                the private repo, or fix the token and delete/recreate this row.
              </p>
            </div>
          )}
        </div>
        <DialogFooter>
          {warning ? (
            <Button onClick={onClose}>Close</Button>
          ) : (
            <>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={!canSubmit || isPending}>
                {submitLabel(isPending, isEdit)}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
