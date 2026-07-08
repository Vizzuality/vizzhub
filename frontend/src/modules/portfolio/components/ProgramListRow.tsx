import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TermChips } from './TermChips';
import { ProjectStatusDot } from './ProjectStatusDot';
import { iterationStats } from '../utils/programs';
import type { ProgramSummary } from '../types/portfolio';

export function ProgramListRow({ program }: { readonly program: ProgramSummary }): JSX.Element {
  const [open, setOpen] = useState(false);
  const stats = iterationStats(program.projects);
  const clients = program.clients.map((c) => c.name).join(', ');
  const subtitle = [clients, stats.yearRange].filter(Boolean).join(' · ');

  return (
    <div className="border-b last:border-b-0">
      <div className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-accent/50">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="-m-1 shrink-0 rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
          aria-label={open ? 'Collapse iterations' : 'Expand iterations'}
        >
          <ChevronRight className={cn('h-4 w-4 transition-transform', open && 'rotate-90')} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Link
              to={`/admin/portfolio/programs/${program.id}`}
              className="truncate text-sm font-medium underline-offset-2 hover:underline"
            >
              {program.name}
            </Link>
            {program.profile?.on_website && (
              <Globe className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
          </div>
          {subtitle && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>

        <div className="hidden w-[38%] min-w-0 shrink-0 lg:block">
          <TermChips terms={program.terms} max={4} />
        </div>

        <div className="w-24 shrink-0 text-right tabular-nums">
          <p className="text-sm leading-tight">
            <span className="font-medium">{stats.active}</span>{' '}
            <span className="text-muted-foreground">active</span>
          </p>
          <p className="text-xs leading-tight text-muted-foreground">
            {stats.finished} finished
          </p>
        </div>
      </div>

      {open && (
        <div className="mb-3 ml-6 space-y-1.5 border-l pl-6 pr-4">
          {program.projects.map((p) => (
            <div key={p.id} className="flex items-center gap-2 py-0.5 text-xs">
              <ProjectStatusDot status={p.status} />
              <span className="truncate text-foreground">{p.name}</span>
              {p.start_year && (
                <span className="text-muted-foreground">
                  {p.start_year}
                  {p.end_year && p.end_year !== p.start_year ? `–${p.end_year}` : ''}
                </span>
              )}
              <span className="text-muted-foreground">{p.status}</span>
            </div>
          ))}
          {program.projects.length === 0 && (
            <span className="text-xs text-muted-foreground">No iterations</span>
          )}
        </div>
      )}
    </div>
  );
}
