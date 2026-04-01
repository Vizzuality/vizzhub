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
import { Switch } from '@/shared/components/ui/switch';
import { Textarea } from '@/shared/components/ui/textarea';
import { RegistryColumnEditor } from './RegistryColumnEditor';
import type { RegistryType, ColumnDef } from '../types/registry';

interface RegistryTypeDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (v: boolean) => void;
  readonly registryType?: RegistryType | null;
  readonly onSave: (data: {
    name: string;
    description: string | null;
    is_yearly: boolean;
    schema: ColumnDef[];
  }) => void;
  readonly isSaving: boolean;
}

export function RegistryTypeDialog({
  open,
  onOpenChange,
  registryType,
  onSave,
  isSaving,
}: RegistryTypeDialogProps): JSX.Element {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isYearly, setIsYearly] = useState(false);
  const [columns, setColumns] = useState<ColumnDef[]>([]);

  useEffect(() => {
    if (open) {
      if (registryType) {
        setName(registryType.name);
        setDescription(registryType.description ?? '');
        setIsYearly(registryType.is_yearly);
        setColumns(registryType.schema);
      } else {
        setName('');
        setDescription('');
        setIsYearly(false);
        setColumns([]);
      }
    }
  }, [open, registryType]);

  const isValid = name.trim().length > 0 && columns.length > 0 &&
    columns.every((c) => c.label.trim() && c.key.trim());

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!isValid) return;
    onSave({
      name: name.trim(),
      description: description.trim() || null,
      is_yearly: isYearly,
      schema: columns,
    });
  };

  const submitLabel = (() => {
    if (isSaving) return 'Saving...';
    return registryType ? 'Save Changes' : 'Create';
  })();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {registryType ? 'Edit Registry Type' : 'New Registry Type'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rt-name">Name</Label>
              <Input
                id="rt-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Asset Inventory"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rt-desc">Description</Label>
              <Textarea
                id="rt-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                rows={2}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={isYearly}
                onCheckedChange={setIsYearly}
                id="rt-yearly"
              />
              <Label htmlFor="rt-yearly">Yearly registry (data partitioned by year)</Label>
            </div>
            <RegistryColumnEditor columns={columns} onChange={setColumns} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isValid || isSaving}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
