import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { MANUAL_KPI_FIELDS } from './constants';
import type { ManualKpiData } from './types';

interface AddKpiDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (data: Record<string, unknown>) => void;
  readonly isLoading: boolean;
}

const REQUIRED_FIELDS = new Set(['name', 'scope', 'responsible', 'methodology', 'formula']);

function getInitialFormState(): Record<string, string> {
  const state: Record<string, string> = {};
  for (const field of MANUAL_KPI_FIELDS) {
    state[field.key] = field.key === 'periodicity' ? 'Mensual' : '';
  }
  return state;
}

export function AddKpiDialog({
  open,
  onClose,
  onSubmit,
  isLoading,
}: AddKpiDialogProps): React.ReactElement {
  const [form, setForm] = useState<Record<string, string>>(getInitialFormState);

  const isValid = [...REQUIRED_FIELDS].every((key) => form[key]?.trim());

  function handleChange(key: string, value: string): void {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    if (!isValid) return;

    const data: ManualKpiData = {
      name: form.name.trim(),
      scope: form.scope.trim(),
      responsible: form.responsible.trim(),
      methodology: form.methodology.trim(),
      formula: form.formula.trim(),
      target: form.target !== '' ? Number(form.target) : null,
      periodicity: form.periodicity,
    };

    onSubmit(data as unknown as Record<string, unknown>);
    setForm(getInitialFormState());
  }

  function handleClose(): void {
    setForm(getInitialFormState());
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Manual KPI</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {MANUAL_KPI_FIELDS.map((field) => (
            <div key={field.key} className="space-y-1">
              <Label htmlFor={`kpi-${field.key}`}>
                {field.label}
                {REQUIRED_FIELDS.has(field.key) && (
                  <span className="text-destructive ml-1">*</span>
                )}
              </Label>
              {field.key === 'methodology' ? (
                <Textarea
                  id={`kpi-${field.key}`}
                  rows={3}
                  value={form[field.key]}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                  disabled={isLoading}
                />
              ) : (
                <Input
                  id={`kpi-${field.key}`}
                  type={field.type === 'number' ? 'number' : 'text'}
                  step={field.type === 'number' ? 'any' : undefined}
                  value={form[field.key]}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                  disabled={isLoading}
                />
              )}
            </div>
          ))}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isValid || isLoading}>
              {isLoading ? 'Adding...' : 'Add KPI'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
