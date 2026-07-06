import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import type { ProjectIteration } from '../types/portfolio';

export function ProgramIterations({
  projects,
  canManage,
  programId: _programId,
}: {
  readonly projects: ProjectIteration[];
  readonly canManage: boolean;
  readonly programId: string;
}): JSX.Element {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium">Iterations</h2>
      <div className="rounded-md border">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 border-b px-3 py-2 text-sm last:border-b-0"
          >
            <span
              className={cn(
                'inline-block h-2 w-2 shrink-0 rounded-full',
                p.status === 'finished' ? 'bg-muted-foreground/50' : 'bg-emerald-500',
              )}
            />
            <span className="min-w-0 flex-1 truncate">{p.name}</span>
            {p.start_year && (
              <span className="text-xs text-muted-foreground">
                {p.start_year}
                {p.end_year && p.end_year !== p.start_year ? `–${p.end_year}` : ''}
              </span>
            )}
            {p.client_name && (
              <span className="hidden text-xs text-muted-foreground md:inline">
                {p.client_name}
              </span>
            )}
            <span className="text-xs text-muted-foreground">{p.status}</span>
            {p.has_scorecard && (
              <Link to={`/scorecard/${p.id}`} className="text-xs underline">
                Scorecard
              </Link>
            )}
            {p.is_billable && !p.is_absence && (
              <Link to={`/tracker/projects/${p.id}`} className="text-xs underline">
                Tracker
              </Link>
            )}
            {canManage && <span data-testid={`iteration-actions-${p.id}`} className="hidden" />}
          </div>
        ))}
        {projects.length === 0 && (
          <p className="px-3 py-4 text-sm text-muted-foreground">No iterations yet.</p>
        )}
      </div>
    </section>
  );
}
