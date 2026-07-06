import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { usePermission, Action } from '@/core/permissions';
import { activeSubItemTo, projectsHubItems } from './sidebarNav';

export function ProjectsHubTabs(): JSX.Element {
  const location = useLocation();
  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canPortfolio = usePermission(Action.PORTFOLIO_VIEW);
  const items = projectsHubItems(bypassAuth || canPortfolio);
  const activeTo = activeSubItemTo(location.pathname, items);

  return (
    <nav className="flex items-center gap-1 border-b">
      {items.map(({ to, label }) => (
        <Link
          key={to}
          to={to}
          aria-current={to === activeTo ? 'page' : undefined}
          className={cn(
            'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            to === activeTo
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground',
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
