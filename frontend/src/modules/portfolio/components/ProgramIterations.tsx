import { useState } from 'react';
import { Link } from 'react-router-dom';
import { MoreHorizontal } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useProgramOptions, useSetProjectProgram } from '../hooks/usePrograms';
import { ProjectStatusDot } from './ProjectStatusDot';
import type { ProjectIteration } from '../types/portfolio';

function MoveIterationDialog({
  open,
  onOpenChange,
  currentProgramId,
  projectName,
  onMove,
}: {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly currentProgramId: string;
  readonly projectName: string;
  readonly onMove: (programId: string) => void;
}): JSX.Element {
  const { data: options } = useProgramOptions();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm gap-0 p-0">
        <DialogHeader className="px-4 pb-2 pt-4">
          <DialogTitle className="text-base">Move “{projectName}” to…</DialogTitle>
        </DialogHeader>
        <Command>
          <CommandInput placeholder="Search programs…" />
          <CommandList>
            <CommandEmpty>No program found.</CommandEmpty>
            <CommandGroup>
              {(options ?? [])
                .filter((o) => o.id !== currentProgramId)
                .map((o) => (
                  <CommandItem key={o.id} value={o.name} onSelect={() => onMove(o.id)}>
                    {o.name}
                  </CommandItem>
                ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

function IterationActions({
  project,
  programId,
}: {
  readonly project: ProjectIteration;
  readonly programId: string;
}): JSX.Element {
  const [moveOpen, setMoveOpen] = useState(false);
  const setProjectProgram = useSetProjectProgram();
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label={`Actions for ${project.name}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setMoveOpen(true)}>
            Move to program…
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() =>
              void setProjectProgram.mutateAsync({ projectId: project.id, programId: null })
            }
          >
            Remove from program
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {moveOpen && (
        <MoveIterationDialog
          open={moveOpen}
          onOpenChange={setMoveOpen}
          currentProgramId={programId}
          projectName={project.name}
          onMove={(target) => {
            void setProjectProgram.mutateAsync({ projectId: project.id, programId: target });
            setMoveOpen(false);
          }}
        />
      )}
    </>
  );
}

export function ProgramIterations({
  projects,
  canManage,
  programId,
}: {
  readonly projects: ProjectIteration[];
  readonly canManage: boolean;
  readonly programId: string;
}): JSX.Element {
  return (
    <section className="space-y-4">
      <h2 className="text-base font-semibold">Iterations</h2>
      <div className="rounded-md border bg-card">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 border-b px-4 py-2.5 text-sm last:border-b-0"
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
            {canManage && <IterationActions project={p} programId={programId} />}
          </div>
        ))}
        {projects.length === 0 && (
          <p className="px-4 py-4 text-sm text-muted-foreground">No iterations yet.</p>
        )}
      </div>
    </section>
  );
}
