import { useEffect, useState, type ReactNode } from 'react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { Button } from '@/shared/components/ui/button';

const MAX_LEN = 500;

interface PlannerCommentPopoverProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly comment?: string;
  readonly onSave: (text: string) => void;
  readonly onDelete?: () => void;
  readonly anchor: ReactNode;
}

export function PlannerCommentPopover({
  open,
  onOpenChange,
  comment,
  onSave,
  onDelete,
  anchor,
}: PlannerCommentPopoverProps): JSX.Element {
  const [draft, setDraft] = useState(comment ?? '');

  useEffect(() => {
    if (open) setDraft(comment ?? '');
  }, [open, comment]);

  const commitSave = (): void => {
    const trimmed = draft.trim();
    if (!trimmed) {
      onOpenChange(false);
      return;
    }
    onSave(trimmed);
    onOpenChange(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      commitSave();
    }
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{anchor}</PopoverTrigger>
      <PopoverContent className="w-72 p-3" align="start" sideOffset={4}>
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_LEN}
          placeholder="Add a note…"
          className="h-24 w-full resize-none rounded border bg-background p-2 text-sm outline-none focus:ring-1 focus:ring-primary"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {draft.length} / {MAX_LEN}
          </span>
          <div className="flex gap-2">
            {comment !== undefined && onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  onDelete();
                  onOpenChange(false);
                }}
              >
                Delete
              </Button>
            )}
            <Button size="sm" onClick={commitSave}>Save</Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
