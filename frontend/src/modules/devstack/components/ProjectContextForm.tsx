import { useState } from 'react';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useAllProjectSummaries } from '@/core/hooks/useProjects';
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
  const { data: projects } = useAllProjectSummaries();
  const createMutation = useCreateProjectContext();
  const updateMutation = useUpdateProjectContext();

  const [projectId, setProjectId] = useState(context?.project_id ?? '');
  const [slug, setSlug] = useState(context?.slug ?? '');
  const [description, setDescription] = useState(context?.description ?? '');
  const [error, setError] = useState<string | null>(null);

  const handleProjectSelect = (id: string): void => {
    setProjectId(id);
    if (!isEdit) {
      const project = (projects ?? []).find((p) => p.id === id);
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
        { onSuccess: onClose },
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
            <Select
              value={projectId}
              onValueChange={handleProjectSelect}
              disabled={isEdit}
            >
              <SelectTrigger id="project">
                <SelectValue placeholder="Select a project" />
              </SelectTrigger>
              <SelectContent>
                {(projects ?? []).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || isPending}>
            {isPending ? 'Saving...' : isEdit ? 'Save' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
