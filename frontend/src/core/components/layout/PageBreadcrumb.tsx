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

interface RouteRule {
  match: string | RegExp;
  crumbs: BreadcrumbSegment[] | ((pathname: string) => BreadcrumbSegment[]);
}

const ROUTE_RULES: RouteRule[] = [
  { match: '/scorecard', crumbs: [{ label: 'Projects' }] },
  { match: '/projects', crumbs: [{ label: 'Projects' }] },
  { match: '/tracker/how-to-report', crumbs: [{ label: 'My Report', to: '/tracker/my-report' }, { label: 'How to Report' }] },
  { match: /^\/iso\/snapshots\//, crumbs: [{ label: 'Access Control', to: '/iso/snapshots' }, { label: 'Snapshot Detail' }] },
  { match: /^\/iso/, crumbs: [{ label: 'Access Control' }] },
  { match: /^\/admin\/notifications/, crumbs: (p) => {
    const sub = p.split('/admin/notifications/')[1];
    return [{ label: 'Notifications', to: '/admin/notifications/log' }, { label: NOTIFICATION_LABELS[sub] ?? sub }];
  }},
  { match: /^\/admin\/tracker\/periods\//, crumbs: [{ label: 'Reporting Periods', to: '/admin/tracker/periods' }, { label: 'Period Detail' }] },
  { match: /^\/admin\/tracker\/invoices/, crumbs: [{ label: 'Invoices' }] },
  { match: /^\/admin\/tracker\/moods/, crumbs: [{ label: 'Moods' }] },
  { match: /^\/admin\/tracker\/periods/, crumbs: [{ label: 'Reporting Periods' }] },
  { match: /^\/admin\/tracker/, crumbs: [{ label: 'Tracker' }] },
  { match: /^\/playbook/, crumbs: [{ label: 'Playbook' }] },
  { match: /^\/iso\/docs/, crumbs: [{ label: 'ISO', to: '/iso/docs' }, { label: 'Documentation' }] },
  { match: /^\/admin/, crumbs: (p) => {
    const sub = p.split('/admin/')[1];
    return [{ label: ADMIN_LABELS[sub] ?? 'Admin' }];
  }},
  { match: /^\/tracker\/projects\/[^/]+$/, crumbs: [{ label: 'Projects', to: '/projects' }, { label: 'Tracker Detail' }] },
  { match: /^\/tracker\/my-reports/, crumbs: [{ label: 'My Report', to: '/tracker/my-report' }, { label: 'Report History' }] },
  { match: /^\/tracker\/my-report/, crumbs: [{ label: 'My Report' }] },
];

function resolvePathBreadcrumbs(pathname: string): BreadcrumbSegment[] | null {
  for (const rule of ROUTE_RULES) {
    const matched = typeof rule.match === 'string'
      ? pathname === rule.match
      : rule.match.test(pathname);
    if (matched) {
      return typeof rule.crumbs === 'function' ? rule.crumbs(pathname) : rule.crumbs;
    }
  }
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
