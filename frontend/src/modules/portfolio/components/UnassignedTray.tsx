import type { ProjectIteration } from '../types/portfolio';

export function UnassignedTray({
  projects,
  canManage,
}: {
  readonly projects: ProjectIteration[];
  readonly canManage: boolean;
}): JSX.Element | null {
  if (projects.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">No program</h2>
      <div className="rounded-md border">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-2 border-b px-3 py-2 text-sm last:border-b-0"
          >
            <span className="flex-1 truncate">{p.name}</span>
            {p.client_name && (
              <span className="text-xs text-muted-foreground">{p.client_name}</span>
            )}
            <span className="text-xs text-muted-foreground">{p.status}</span>
            {canManage && <span data-testid="assign-slot" className="hidden" />}
          </div>
        ))}
      </div>
    </section>
  );
}
