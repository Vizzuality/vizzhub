import { useState, useEffect } from 'react';
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

interface NodeFormProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (title: string, type: 'page' | 'group' | 'registry', registryTypeId?: string) => void;
  readonly isLoading: boolean;
  readonly parentId: string | null;
  readonly dialogTitle?: string;
  readonly rootLabel?: string;
  readonly renderRegistryPicker?: (value: string | null, onChange: (id: string) => void) => React.ReactNode;
}

export function NodeForm({
  open,
  onClose,
  onSubmit,
  isLoading,
  parentId,
  dialogTitle,
  rootLabel = 'Add to root',
  renderRegistryPicker,
}: NodeFormProps): JSX.Element {
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'page' | 'group' | 'registry'>('page');
  const [registryTypeId, setRegistryTypeId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setTitle('');
      setType('page');
      setRegistryTypeId(null);
    }
  }, [open]);

  const canSubmit = title.trim() && (type !== 'registry' || registryTypeId);

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (canSubmit) {
      onSubmit(title.trim(), type, type === 'registry' ? registryTypeId! : undefined);
    }
  };

  const resolvedTitle = dialogTitle ?? (parentId ? 'Add to group' : rootLabel);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{resolvedTitle}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Type</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={type === 'page' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setType('page')}
                >
                  Page
                </Button>
                <Button
                  type="button"
                  variant={type === 'group' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setType('group')}
                >
                  Group
                </Button>
                {renderRegistryPicker && (
                  <Button
                    type="button"
                    variant={type === 'registry' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setType('registry')}
                  >
                    Registry
                  </Button>
                )}
              </div>
            </div>
            {type === 'registry' && renderRegistryPicker && (
              <div className="space-y-2">
                <Label>Registry Type</Label>
                {renderRegistryPicker(registryTypeId, setRegistryTypeId)}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={type === 'registry' ? 'Registry name' : type === 'page' ? 'Page title' : 'Group name'}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit || isLoading}>
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
