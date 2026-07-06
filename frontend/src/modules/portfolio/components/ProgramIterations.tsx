import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { useSetProjectProgram } from '../hooks/usePrograms';
import { ProgramCombobox } from './ProgramCombobox';
import { ProjectStatusDot } from './ProjectStatusDot';
import type { ProjectIteration } from '../types/portfolio';

export function ProgramIterations({
  projects,
  canManage,
  programId,
}: {
  readonly projects: ProjectIteration[];
  readonly canManage: boolean;
  readonly programId: string;
}): JSX.Element {
  const setProjectProgram = useSetProjectProgram();
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium">Iterations</h2>
      <div className="rounded-md border">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 border-b px-3 py-2 text-sm last:border-b-0"
          >
            <ProjectStatusDot status={p.status} />
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
            {canManage && (
              <>
                <ProgramCombobox
                  triggerLabel="Move…"
                  value={programId}
                  onSelect={(target) => {
                    if (target !== programId) {
                      void setProjectProgram.mutateAsync({ projectId: p.id, programId: target });
                    }
                  }}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void setProjectProgram.mutateAsync({ projectId: p.id, programId: null })}
                >
                  Remove
                </Button>
              </>
            )}
          </div>
        ))}
        {projects.length === 0 && (
          <p className="px-3 py-4 text-sm text-muted-foreground">No iterations yet.</p>
        )}
      </div>
    </section>
  );
}
