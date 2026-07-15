import { cn } from '@/lib/utils';
import { getStatusLabel } from '@/utils/projectStatus';

// Status display convention: colored dot + plain text, never tinted pills.
const STATUS_DOT_CLASSES: Record<string, string> = {
  proposal: 'bg-score-yellow',
  live: 'bg-score-green',
  finished: 'bg-muted-foreground',
};

export function StatusBadge({ status }: { readonly status: string }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1.5 shrink-0 text-xs font-medium text-muted-foreground whitespace-nowrap">
      <span
        className={cn(
          'inline-block w-2 h-2 rounded-full shrink-0',
          STATUS_DOT_CLASSES[status] ?? 'bg-muted-foreground',
        )}
      />
      {getStatusLabel(status)}
    </span>
  );
}
