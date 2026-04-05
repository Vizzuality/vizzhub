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
import type { DocNodeType } from '@/shared/types/doc';

interface NodeFormProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (title: string, type: DocNodeType, registryTypeId?: string, widgetKey?: string) => void;
  readonly isLoading: boolean;
  readonly parentId: string | null;
  readonly dialogTitle?: string;
  readonly rootLabel?: string;
  readonly renderRegistryPicker?: (value: string | null, onChange: (id: string) => void) => React.ReactNode;
  readonly showWidgetOption?: boolean;
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
  showWidgetOption,
}: NodeFormProps): JSX.Element {
  const [title, setTitle] = useState('');
  const [type, setType] = useState<DocNodeType>('page');
  const [registryTypeId, setRegistryTypeId] = useState<string | null>(null);
  const [widgetKey, setWidgetKey] = useState('');

  useEffect(() => {
    if (open) {
      setTitle('');
      setType('page');
      setRegistryTypeId(null);
      setWidgetKey('');
    }
  }, [open]);

  const canSubmit = title.trim()
    && (type !== 'registry' || registryTypeId)
    && (type !== 'widget' || widgetKey.trim());

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (canSubmit) {
      onSubmit(
        title.trim(),
        type,
        type === 'registry' ? registryTypeId! : undefined,
        type === 'widget' ? widgetKey.trim() : undefined,
      );
    }
  };

  const resolvedTitle = dialogTitle ?? (parentId ? 'Add to group' : rootLabel);
  const placeholderByType: Record<string, string> = {
    registry: 'Registry name',
    page: 'Page title',
    group: 'Group name',
    widget: 'Widget title',
  };

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
                {showWidgetOption && (
                  <Button
                    type="button"
                    variant={type === 'widget' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setType('widget')}
                  >
                    Widget
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
            {type === 'widget' && (
              <div className="space-y-2">
                <Label htmlFor="widget-key">Widget Key</Label>
                <Input
                  id="widget-key"
                  value={widgetKey}
                  onChange={(e) => setWidgetKey(e.target.value)}
                  placeholder="e.g. management-review-report"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={placeholderByType[type]}
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
