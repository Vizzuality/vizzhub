import { cn } from '@/lib/utils';

interface NativeSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  children: React.ReactNode;
}

export function NativeSelect({
  className,
  children,
  ...props
}: NativeSelectProps): JSX.Element {
  return (
    <select
      className={cn(
        'h-10 rounded-md border border-input bg-background px-3 py-2 text-sm',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
