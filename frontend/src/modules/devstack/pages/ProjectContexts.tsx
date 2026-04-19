import { useState } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  useProjectContexts,
  useDeleteProjectContext,
} from '../hooks/useProjectContexts';
import { ProjectContextForm } from '../components/ProjectContextForm';
import type { ProjectContext } from '../types/projectContexts';

export default function ProjectContexts(): JSX.Element {
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const { data, isLoading } = useProjectContexts();
  const deleteMutation = useDeleteProjectContext();

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ProjectContext | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectContext | null>(null);

  const handleDelete = (): void => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  if (isLoading) return <LoadingSpinner />;

  const contexts = data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Project Contexts</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Per-project private CLAUDE.md files synced via DevStack.
          </p>
        </div>
        {canManage && (
          <Button
            size="sm"
            onClick={() => {
              setEditTarget(null);
              setFormOpen(true);
            }}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Project Context
          </Button>
        )}
      </div>

      {contexts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground">No project contexts yet</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Description</TableHead>
                  {canManage && (
                    <TableHead className="w-[100px]">Actions</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {contexts.map((ctx) => (
                  <TableRow key={ctx.id}>
                    <TableCell className="font-medium">
                      {ctx.project_name ?? '—'}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {ctx.slug}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {ctx.description ?? '—'}
                    </TableCell>
                    {canManage && (
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditTarget(ctx);
                              setFormOpen(true);
                            }}
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteTarget(ctx)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {canManage && formOpen && (
        <ProjectContextForm
          context={editTarget}
          onClose={() => {
            setFormOpen(false);
            setEditTarget(null);
          }}
        />
      )}

      <AlertDialog
        open={canManage && deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project context?</AlertDialogTitle>
            <AlertDialogDescription>
              This unlinks &quot;{deleteTarget?.slug}&quot; from VizzHub. The
              private CLAUDE.md file in the GitHub repo is not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                handleDelete();
              }}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
