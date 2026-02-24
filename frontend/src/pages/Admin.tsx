import { NavLink, Outlet, Navigate, useMatch } from 'react-router-dom';
import { cn } from '@/lib/utils';

const TABS = [
  { to: 'global-scores', label: 'Global Scores' },
  { to: 'scorecard-parameters', label: 'Scorecard Parameters' },
  { to: 'integrations', label: 'Integrations' },
  { to: 'notifications', label: 'Notifications' },
  { to: 'jobs', label: 'Jobs' },
  { to: 'users', label: 'Users' },
] as const;

export default function Admin(): JSX.Element {
  const isIndex = useMatch('/admin');

  if (isIndex) {
    return <Navigate to="global-scores" replace />;
  }

  return (
    <div className="space-y-6">
      <nav className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
        {TABS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to !== 'notifications'}
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
