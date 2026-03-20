import { NavLink, Outlet, Navigate, useMatch } from 'react-router-dom';
import { cn } from '@/lib/utils';

const SUB_TABS = [
  { to: 'periods', label: 'Reporting Periods' },
  { to: 'invoices', label: 'Invoices' },
] as const;

export default function TrackerLayout(): JSX.Element {
  const isIndex = useMatch('/admin/tracker');

  if (isIndex) {
    return <Navigate to="periods" replace />;
  }

  return (
    <div className="space-y-4">
      <nav className="flex gap-1 border-b border-border pb-px">
        {SUB_TABS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'inline-flex items-center justify-center whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
                isActive
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
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
