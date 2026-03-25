import { Link, useLocation, useParams } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useProject } from '@/core/hooks/useProjects';

interface BreadcrumbSegment {
  label: string;
  to?: string;
}

const ADMIN_LABELS: Record<string, string> = {
  'global-scores': 'Global Scores',
  'scorecard-parameters': 'Scorecard Parameters',
  integrations: 'Integrations',
  jobs: 'Jobs',
  users: 'Users',
};

const NOTIFICATION_LABELS: Record<string, string> = {
  log: 'Alert Log',
  silences: 'Active Silences',
  config: 'Configuration',
  stats: 'Statistics',
};

function resolvePathBreadcrumbs(pathname: string): BreadcrumbSegment[] | null {
  if (pathname === '/scorecard') return [{ label: 'Projects' }];
  if (pathname === '/projects') return [{ label: 'Projects' }];
  if (pathname === '/tracker/how-to-report') {
    return [{ label: 'My Report', to: '/tracker/my-report' }, { label: 'How to Report' }];
  }

  if (pathname.startsWith('/iso/snapshots/')) {
    return [{ label: 'Access Control', to: '/iso/snapshots' }, { label: 'Snapshot Detail' }];
  }
  if (pathname.startsWith('/iso')) return [{ label: 'Access Control' }];

  if (pathname.startsWith('/admin/notifications')) {
    const subPath = pathname.split('/admin/notifications/')[1];
    return [
      { label: 'Notifications', to: '/admin/notifications/log' },
      { label: NOTIFICATION_LABELS[subPath] ?? subPath },
    ];
  }
  if (pathname.startsWith('/admin/tracker/periods/')) {
    return [{ label: 'Reporting Periods', to: '/admin/tracker/periods' }, { label: 'Period Detail' }];
  }
  if (pathname.startsWith('/admin/tracker/invoices')) return [{ label: 'Invoices' }];
  if (pathname.startsWith('/admin/tracker/moods')) return [{ label: 'Moods' }];
  if (pathname.startsWith('/admin/tracker/periods')) return [{ label: 'Reporting Periods' }];
  if (pathname.startsWith('/admin/tracker')) return [{ label: 'Tracker' }];
  if (pathname.startsWith('/playbook')) return [{ label: 'Playbook' }];

  if (pathname.startsWith('/admin')) {
    const subPath = pathname.split('/admin/')[1];
    return [{ label: ADMIN_LABELS[subPath] ?? 'Admin' }];
  }

  if (pathname.match(/^\/tracker\/projects\/[^/]+$/)) {
    return [{ label: 'Projects', to: '/projects' }, { label: 'Tracker Detail' }];
  }
  if (pathname.startsWith('/tracker/my-reports')) {
    return [{ label: 'My Report', to: '/tracker/my-report' }, { label: 'Report History' }];
  }
  if (pathname.startsWith('/tracker/my-report')) return [{ label: 'My Report' }];

  return null;
}

function useBreadcrumbs(): BreadcrumbSegment[] {
  const location = useLocation();
  const { id } = useParams<{ id: string }>();
  const pathname = location.pathname;

  const isProjectDetail = pathname.match(/^\/scorecard\/[^/]+$/);
  const { data: project } = useProject(isProjectDetail && id ? id : '');

  if (isProjectDetail) {
    return [
      { label: 'Projects', to: '/scorecard' },
      { label: project?.name ?? 'Project' },
    ];
  }

  return resolvePathBreadcrumbs(pathname) ?? [{ label: 'Dashboard' }];
}

export function PageBreadcrumb(): JSX.Element {
  const breadcrumbs = useBreadcrumbs();

  return (
    <nav className="flex items-center gap-1.5 text-sm">
      {breadcrumbs.map((segment, i) => {
        const isLast = i === breadcrumbs.length - 1;
        return (
          <span key={segment.to ?? segment.label} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
            {segment.to && !isLast ? (
              <Link
                to={segment.to}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {segment.label}
              </Link>
            ) : (
              <span className="font-medium text-foreground">{segment.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
