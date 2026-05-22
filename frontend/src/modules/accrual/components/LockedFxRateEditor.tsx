import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '@/core/services/projects';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';

interface LockedFxRateEditorProps {
  readonly projectId: string;
  readonly projectCurrency: string;
  readonly currentRate: string | null;
  readonly canEdit: boolean;
}

const fmt = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 6,
});

export function LockedFxRateEditor({
  projectId,
  projectCurrency,
  currentRate,
  canEdit,
}: LockedFxRateEditorProps): JSX.Element {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(currentRate ?? '');

  const mutation = useMutation({
    mutationFn: (locked_fx_rate: number | null) =>
      projectsApi.update(projectId, { locked_fx_rate }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accrual.cells.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all });
      setOpen(false);
    },
  });

  const display = currentRate ? fmt.format(Number(currentRate)) : '—';

  if (!canEdit) {
    return <span className="text-xs tabular-nums text-muted-foreground">{display}</span>;
  }

  const handleSave = (): void => {
    const parsed = Number(draft);
    if (!draft.trim() || Number.isNaN(parsed) || parsed <= 0) return;
    mutation.mutate(parsed);
  };

  const handleClear = (): void => {
    setDraft('');
    mutation.mutate(null);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setDraft(currentRate ?? '');
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="w-full text-left text-xs tabular-nums text-foreground hover:underline"
          aria-label={`Set FX lock for ${projectCurrency}`}
        >
          {display}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 space-y-3 p-3" align="start">
        <div>
          <p className="text-xs text-muted-foreground">
            FX lock for this project ({projectCurrency} → EUR rate)
          </p>
          <p className="text-[11px] text-muted-foreground">
            Falls back to period rate, then ECB, if cleared.
          </p>
        </div>
        <Input
          type="number"
          step="0.000001"
          min="0"
          inputMode="decimal"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave();
            if (e.key === 'Escape') setOpen(false);
          }}
        />
        <div className="flex items-center justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={!currentRate || mutation.isPending}
            onClick={handleClear}
          >
            Clear
          </Button>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              disabled={mutation.isPending || !draft.trim()}
            >
              Save
            </Button>
          </div>
        </div>
        {mutation.error && (
          <p className="text-xs text-destructive">Could not save FX lock.</p>
        )}
      </PopoverContent>
    </Popover>
  );
}
