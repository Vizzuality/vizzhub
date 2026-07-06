import { cn } from '@/lib/utils';

export function ProjectStatusDot({ status }: { readonly status: string }): JSX.Element {
  return (
    <span
      className={cn(
        'inline-block h-2 w-2 shrink-0 rounded-full',
        status === 'finished' ? 'bg-muted-foreground/50' : 'bg-emerald-500',
      )}
    />
  );
}
