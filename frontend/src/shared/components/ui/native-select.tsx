import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface NativeSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  readonly children: React.ReactNode;
}

export const NativeSelect = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-10 rounded-md border border-input bg-background px-3 py-2 text-sm',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);

NativeSelect.displayName = 'NativeSelect';
