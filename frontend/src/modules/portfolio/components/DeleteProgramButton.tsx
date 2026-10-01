import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
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
import { getApiErrorMessage } from '@/utils/apiErrors';
import { useDeleteProgram } from '../hooks/usePrograms';
import type { ProgramSummary } from '../types/portfolio';

/** Deletes an empty program; programs with projects must have them reassigned first. */
export function DeleteProgramButton({
  program,
  onDeleted,
}: {
  readonly program: ProgramSummary;
  readonly onDeleted: () => void;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deleteProgram = useDeleteProgram(program.id);
  const hasProjects = program.projects.length > 0;

  const handleConfirm = async (): Promise<void> => {
    setError(null);
    try {
      await deleteProgram.mutateAsync();
      setOpen(false);
      onDeleted();
    } catch (err) {
      setError(getApiErrorMessage(err as Error, { fallback: 'Could not delete the program' }));
    }
  };

  return (
    <>
      <span title={hasProjects ? 'Reassign its projects before deleting the program' : undefined}>
        <Button
          variant="outline"
          size="sm"
          aria-label="Delete program"
          disabled={hasProjects}
          onClick={() => {
            setError(null);
            setOpen(true);
          }}
        >
          <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
        </Button>
      </span>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete program</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{program.name}</strong>? Its portfolio
              content, tags and links will be removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteProgram.isPending}
              onClick={(e) => {
                e.preventDefault();
                void handleConfirm();
              }}
            >
              {deleteProgram.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
