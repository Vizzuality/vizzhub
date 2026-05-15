import { useState } from 'react';
import { Pencil, Trash2, Plus } from 'lucide-react';
import { useRates, useCreateRate, useUpdateRate, useDeleteRate } from '../../hooks/useUsers';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
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
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';

interface RateFormState {
  id?: string;
  code: string;
  value: string;
}

const EMPTY_FORM: RateFormState = { code: '', value: '' };

export function RatesContent(): JSX.Element {
  const { data: rates, isLoading, error } = useRates();
  const createRate = useCreateRate();
  const updateRate = useUpdateRate();
  const deleteRate = useDeleteRate();

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<RateFormState>(EMPTY_FORM);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const isEditing = !!form.id;

  const handleOpenCreate = (): void => {
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const handleOpenEdit = (rate: { id: string; code: string; value: number }): void => {
    setForm({ id: rate.id, code: rate.code, value: String(rate.value) });
    setFormOpen(true);
  };

  const handleSubmit = (): void => {
    const value = Number.parseFloat(form.value);
    if (!form.code.trim() || Number.isNaN(value)) return;

    if (isEditing) {
      updateRate.mutate(
        { id: form.id!, data: { code: form.code.trim(), value } },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createRate.mutate(
        { code: form.code.trim(), value },
        { onSuccess: () => setFormOpen(false) },
      );
    }
  };

  const handleDelete = (): void => {
    if (!deleteId) return;
    deleteRate.mutate(deleteId, {
      onSuccess: () => setDeleteId(null),
    });
  };

  if (isLoading) return <LoadingSpinner className="py-8" />;

  if (error) {
    return (
      <div className="text-destructive text-center py-8">
        Error loading rates: {error.message}
      </div>
    );
  }

  const isSaving = createRate.isPending || updateRate.isPending;
  let submitLabel: string;
  if (isSaving) submitLabel = 'Saving...';
  else if (isEditing) submitLabel = 'Save';
  else submitLabel = 'Create';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{rates?.length ?? 0} rate bands</p>
        <Button size="sm" onClick={handleOpenCreate}>
          <Plus className="h-4 w-4 mr-1" />
          Add rate
        </Button>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Code</th>
              <th className="text-left p-3 font-medium">Value</th>
              <th className="w-[100px] p-3"></th>
            </tr>
          </thead>
          <tbody>
            {rates?.map((rate) => (
              <tr key={rate.id} className="border-t">
                <td className="p-3 font-medium">{rate.code}</td>
                <td className="p-3 text-muted-foreground tabular-nums">
                  {Number(rate.value).toLocaleString('en', { minimumFractionDigits: 2 })}
                </td>
                <td className="p-3">
                  <div className="flex items-center gap-1 justify-end">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleOpenEdit(rate)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => setDeleteId(rate.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {rates?.length === 0 && (
              <tr>
                <td colSpan={3} className="p-6 text-center text-muted-foreground text-sm">
                  No rate bands configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>{isEditing ? 'Edit rate' : 'New rate'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="rate-code">Code</Label>
              <Input
                id="rate-code"
                placeholder="e.g. A, B, C..."
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rate-value">Value</Label>
              <Input
                id="rate-value"
                type="number"
                min={0}
                step="0.01"
                placeholder="0.00"
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>Cancel</Button>
            <Button
              onClick={handleSubmit}
              disabled={!form.code.trim() || !form.value || isSaving}
            >
              {submitLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete rate</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this rate band? Users assigned to it will become unassigned.
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
              {deleteRate.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
