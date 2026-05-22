import { Check, Loader2 } from 'lucide-react';

interface SaveIndicatorProps {
  readonly isSaving: boolean;
  readonly pendingCount: number;
}

export function SaveIndicator({
  isSaving,
  pendingCount,
}: SaveIndicatorProps): JSX.Element | null {
  if (isSaving) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Saving...
      </span>
    );
  }

  if (pendingCount > 0) {
    return (
      <span className="text-xs text-muted-foreground">
        {pendingCount} unsaved
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Check className="h-3 w-3" />
      Saved
    </span>
  );
}
