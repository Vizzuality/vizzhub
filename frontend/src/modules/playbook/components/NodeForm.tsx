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

interface NodeFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (title: string, type: 'page' | 'group') => void;
  isLoading: boolean;
  parentId: string | null;
}

export function NodeForm({
  open,
  onClose,
  onSubmit,
  isLoading,
  parentId,
}: NodeFormProps): JSX.Element {
  const [title, setTitle] = useState('');
  const [type, setType] = useState<'page' | 'group'>('page');

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (title.trim()) {
      onSubmit(title.trim(), type);
      setTitle('');
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {parentId ? 'Add to group' : 'Add to playbook'}
            </DialogTitle>
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
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={type === 'page' ? 'Page title' : 'Group name'}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!title.trim() || isLoading}>
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
