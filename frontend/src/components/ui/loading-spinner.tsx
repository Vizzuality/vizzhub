interface LoadingSpinnerProps {
  readonly className?: string;
}

export function LoadingSpinner({ className = 'h-64' }: LoadingSpinnerProps): JSX.Element {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}
