import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';

export default function PortfolioLayout(): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const tabs = [
    { to: '/admin/portfolio', label: 'Clients', end: true },
    { to: '/admin/portfolio/dashboard', label: 'Dashboard', end: false },
    ...(canManage ? [{ to: '/admin/portfolio/import', label: 'Import', end: false }] : []),
  ];
  return (
    <div className="space-y-4">
      <nav className="flex gap-1 border-b">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              cn(
                'px-3 py-2 text-sm border-b-2 -mb-px',
                isActive
                  ? 'border-foreground text-foreground font-medium'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
