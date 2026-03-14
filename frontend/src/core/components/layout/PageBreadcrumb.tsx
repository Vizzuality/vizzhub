import { Link, useLocation, useParams } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useProject } from '@/core/hooks/useProjects';

interface BreadcrumbSegment {
  label: string;
  to?: string;
}

function useBreadcrumbs(): BreadcrumbSegment[] {
  const location = useLocation();
  const { id } = useParams<{ id: string }>();
  const pathname = location.pathname;

  const isProjectDetail = pathname.match(/^\/scorecard\/[^/]+$/);
  const { data: project } = useProject(isProjectDetail && id ? id : '');

  if (pathname === '/scorecard') {
    return [{ label: 'Projects' }];
  }

  if (isProjectDetail) {
    return [
      { label: 'Projects', to: '/scorecard' },
      { label: project?.name ?? 'Project' },
    ];
  }

  if (pathname.startsWith('/iso/snapshots/')) {
    return [
      { label: 'Access Control', to: '/iso/snapshots' },
      { label: 'Snapshot Detail' },
    ];
  }

  if (pathname.startsWith('/iso')) {
    return [{ label: 'Access Control' }];
  }

  if (pathname.startsWith('/admin/notifications')) {
    const subPath = pathname.split('/admin/notifications/')[1];
    const subLabels: Record<string, string> = {
      log: 'Alert Log',
      silences: 'Active Silences',
      config: 'Configuration',
      stats: 'Statistics',
    };
    return [
      { label: 'Notifications', to: '/admin/notifications/log' },
      { label: subLabels[subPath] ?? subPath },
    ];
  }

  if (pathname.startsWith('/admin')) {
    const adminLabels: Record<string, string> = {
      'global-scores': 'Global Scores',
      'scorecard-parameters': 'Scorecard Parameters',
      integrations: 'Integrations',
      jobs: 'Jobs',
      users: 'Users',
    };
    const subPath = pathname.split('/admin/')[1];
    return [{ label: adminLabels[subPath] ?? 'Admin' }];
  }

  return [{ label: 'Dashboard' }];
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
