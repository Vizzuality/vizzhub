import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { useMergeClients } from '../hooks/useClients';
import type { Client } from '../types/portfolio';

interface ClientMergeDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly candidates: Client[];
  readonly onMerged: () => void;
}

export function ClientMergeDialog({
  open, onOpenChange, candidates, onMerged,
}: ClientMergeDialogProps): JSX.Element {
  const merge = useMergeClients();
  const [targetId, setTargetId] = useState<string>('');

  useEffect(() => {
    if (open && candidates.length > 0) setTargetId(candidates[0].id);
  }, [open, candidates]);

  const handleMerge = async (): Promise<void> => {
    const sourceIds = candidates.filter((c) => c.id !== targetId).map((c) => c.id);
    if (sourceIds.length === 0) return;
    await merge.mutateAsync({ targetId, data: { source_ids: sourceIds } });
    onMerged();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Merge clients</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <p className="text-sm text-muted-foreground">
            Choose the canonical client. The others are merged into it and their projects reassigned.
          </p>
          <div className="space-y-2">
            {candidates.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="merge-target"
                  checked={targetId === c.id}
                  onChange={() => setTargetId(c.id)}
                />
                <span className="font-medium text-foreground">{c.name}</span>
                <span className="text-muted-foreground">({c.project_count} projects)</span>
              </label>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleMerge} disabled={merge.isPending}>
            {merge.isPending ? 'Merging...' : 'Merge'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
