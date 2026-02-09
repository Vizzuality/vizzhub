import { NavLink, Outlet, Navigate, useMatch } from 'react-router-dom';
import { cn } from '@/lib/utils';

const SUB_TABS = [
  { to: 'log', label: 'Alert Log' },
  { to: 'silences', label: 'Active Silences' },
  { to: 'config', label: 'Alert Configuration' },
  { to: 'stats', label: 'Statistics' },
] as const;

export default function AdminNotificationsLayout(): JSX.Element {
  const isIndex = useMatch('/admin/notifications');

  if (isIndex) {
    return <Navigate to="log" replace />;
  }

  return (
    <div className="mt-4 space-y-2">
      <nav className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
        {SUB_TABS.map(({ to, label }) => (
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
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
