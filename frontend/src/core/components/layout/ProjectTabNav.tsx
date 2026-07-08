import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { usePermission, Action } from '@/core/permissions';
import { useProjectContext } from '@/core/contexts/ProjectContext';

interface FacetTab {
  readonly key: string;
  readonly label: string;
  readonly show: boolean;
}

export function ProjectTabNav(): JSX.Element {
  const { project, projectId } = useProjectContext();
  const canScorecard = usePermission(Action.SCORECARD_VIEW);
  const canTracker = usePermission(Action.TRACKER_VIEW);

  const tabs: FacetTab[] = [
    { key: 'tracker', label: 'Tracker', show: canTracker },
    { key: 'scorecard', label: 'Scorecard', show: canScorecard && project.has_scorecard },
  ];

  return (
    <nav className="flex items-center gap-1 border-b">
      {tabs.filter((t) => t.show).map((t) => (
        <NavLink
          key={t.key}
          to={`/projects/${projectId}/${t.key}`}
          className={({ isActive }) =>
            cn(
              'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              isActive
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
