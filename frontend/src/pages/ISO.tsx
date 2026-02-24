import { NavLink, Outlet, Navigate, useMatch } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useIsoSnapshots } from '@/hooks/useIso';
import { isSnapshotStale } from '@/hooks/isoStaleCheck';

const TABS = [
  { to: 'snapshots', label: 'Snapshots' },
  { to: 'config', label: 'Configuration' },
] as const;

export default function ISO(): JSX.Element {
  const isIndex = useMatch('/iso');
  const { data: snapshotData } = useIsoSnapshots({ page: 1, page_size: 1 });
  const latestCapturedAt = snapshotData?.items?.[0]?.captured_at ?? null;
  const snapshotsStale = isSnapshotStale(latestCapturedAt);

  if (isIndex) {
    return <Navigate to="snapshots" replace />;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">ISO Compliance</h1>

      <nav className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
        {TABS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isActive
                  ? 'bg-background text-foreground shadow'
                  : 'hover:bg-background/50 hover:text-foreground',
              )
            }
          >
            {label}
            {to === 'snapshots' && snapshotsStale && (
              <span className="ml-1.5 h-2 w-2 rounded-full bg-amber-500 inline-block" />
            )}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
