import { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
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
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { EntryForm } from '../components/EntryForm';
import { useDevstackEntries, useDeleteDevstackEntry } from '../hooks/useDevstack';
import { ENTRY_TYPES } from '../types/devstack';

const ALL_TYPES = '__all__';

function StatusDot({ on, onColor = 'bg-green-500' }: {
  readonly on: boolean;
  readonly onColor?: string;
}): JSX.Element {
  return (
    <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${on ? onColor : 'bg-muted-foreground/40'}`} />
  );
}

export default function Catalog(): JSX.Element {
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const params = typeFilter ? { type: typeFilter } : {};
  const { data, isLoading } = useDevstackEntries(params);
  const deleteEntry = useDeleteDevstackEntry();

  const entries = data?.items ?? [];

  const handleDeleteConfirm = (): void => {
    if (!deleteTarget) return;
    deleteEntry.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">DevStack Catalog</h1>
        {canManage && (
          <Button size="sm" onClick={() => setSelectedId('new')}>
            <Plus className="w-4 h-4 mr-1.5" />
            Add Entry
          </Button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Select
          value={typeFilter || ALL_TYPES}
          onValueChange={(v) => setTypeFilter(v === ALL_TYPES ? '' : v)}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_TYPES}>All types</SelectItem>
            {ENTRY_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
        </span>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">
          {typeFilter ? 'No entries match the selected type.' : 'No catalog entries yet.'}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Required</TableHead>
              <TableHead>Origin</TableHead>
              <TableHead>Active</TableHead>
              {canManage && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="font-medium">{entry.name}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{entry.type}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{entry.install_method}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <StatusDot on={entry.required} />
                    <span className="text-sm text-foreground">{entry.required ? 'Yes' : 'No'}</span>
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{entry.origin}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <StatusDot on={entry.active} />
                    <span className="text-sm text-foreground">{entry.active ? 'Active' : 'Inactive'}</span>
                  </div>
                </TableCell>
                {canManage && (
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => setSelectedId(entry.id)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget({ id: entry.id, name: entry.name })}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {selectedId !== null && (
        <EntryForm selectedId={selectedId} onClose={() => setSelectedId(null)} />
      )}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete entry?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{deleteTarget?.name}&quot; from the catalog.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => { e.preventDefault(); handleDeleteConfirm(); }}
            >
              {deleteEntry.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
