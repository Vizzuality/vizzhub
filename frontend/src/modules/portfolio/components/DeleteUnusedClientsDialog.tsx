import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { getApiErrorDetail } from '@/utils/apiErrors';
import { useDeleteUnusedClients, useUnusedClients } from '../hooks/useClients';

interface DeleteUnusedClientsDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

/** Bulk delete of clients no project uses; the Copper import recreates them on demand. */
export function DeleteUnusedClientsDialog({
  open,
  onOpenChange,
}: DeleteUnusedClientsDialogProps): JSX.Element {
  const { data: unused, isLoading } = useUnusedClients(open);
  const remove = useDeleteUnusedClients();
  const count = unused?.length ?? 0;

  const close = (next: boolean): void => {
    if (!next) remove.reset();
    onOpenChange(next);
  };

  let body: JSX.Element;
  if (remove.isSuccess) {
    body = <p className="text-sm text-foreground">Deleted {remove.data.deleted} clients.</p>;
  } else if (isLoading) {
    body = <p className="text-sm text-muted-foreground">Looking for clients without projects…</p>;
  } else if (count === 0) {
    body = <p className="text-sm text-muted-foreground">Every client has at least one project.</p>;
  } else {
    body = (
      <>
        <p className="text-sm text-foreground">
          {count} clients have no projects and will be deleted:
        </p>
        <ul className="max-h-64 overflow-y-auto rounded-md border px-3 py-2 text-sm text-muted-foreground">
          {unused?.map((c) => <li key={c.id}>{c.name}</li>)}
        </ul>
      </>
    );
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete clients without projects</DialogTitle>
          <DialogDescription>
            Copper is the client catalogue: importing an opportunity creates its client again.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {body}
          {remove.isError && (
            <p className="text-sm text-destructive">
              {getApiErrorDetail(remove.error, 'Could not delete the clients.')}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {remove.isSuccess ? 'Close' : 'Cancel'}
          </Button>
          {!remove.isSuccess && (
            <Button
              variant="destructive"
              disabled={count === 0 || remove.isPending}
              onClick={() => remove.mutate()}
            >
              {remove.isPending ? 'Deleting...' : `Delete ${count} clients`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
