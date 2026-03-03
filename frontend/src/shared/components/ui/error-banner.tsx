interface ErrorBannerProps {
  readonly message: string;
}

export function ErrorBanner({ message }: ErrorBannerProps): JSX.Element {
  return (
    <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
      {message}
    </div>
  );
}
