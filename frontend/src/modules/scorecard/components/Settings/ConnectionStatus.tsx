import { cn } from '@/lib/utils';

interface ConnectionStatusProps {
  connected: boolean;
}

export function ConnectionStatus({ connected }: Readonly<ConnectionStatusProps>): JSX.Element {
  return (
    <span className="flex items-center gap-2 text-sm text-foreground whitespace-nowrap">
      <span
        className={cn(
          'inline-block w-2 h-2 rounded-full shrink-0',
          connected ? 'bg-green-500' : 'bg-muted-foreground'
        )}
      />
      {connected ? 'Connected' : 'Not connected'}
    </span>
  );
}
