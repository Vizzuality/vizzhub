import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TermChips } from './TermChips';
import { iterationSummary } from '../utils/programs';
import type { ProgramSummary } from '../types/portfolio';

export function ProgramListRow({ program }: { readonly program: ProgramSummary }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b last:border-b-0">
      <div className="flex items-center gap-3 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 text-muted-foreground"
          aria-label={open ? 'Collapse iterations' : 'Expand iterations'}
        >
          <ChevronRight className={cn('h-4 w-4 transition-transform', open && 'rotate-90')} />
        </button>
        <Link
          to={`/admin/portfolio/programs/${program.id}`}
          className="min-w-0 flex-1 truncate text-sm font-medium hover:underline"
        >
          {program.name}
        </Link>
        <span className="hidden max-w-40 truncate text-xs text-muted-foreground md:inline">
          {program.clients.map((c) => c.name).join(', ')}
        </span>
        <div className="hidden lg:block">
          <TermChips terms={program.terms} max={4} />
        </div>
        <span className="w-40 shrink-0 text-right text-xs text-muted-foreground">
          {iterationSummary(program.projects)}
        </span>
        {program.profile?.on_website && (
          <Globe className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
      </div>
      {open && (
        <div className="space-y-1 px-10 pb-2">
          {program.projects.map((p) => (
            <div key={p.id} className="flex items-center gap-2 text-xs text-muted-foreground">
              <span
                className={cn(
                  'inline-block h-2 w-2 shrink-0 rounded-full',
                  p.status === 'finished' ? 'bg-muted-foreground/50' : 'bg-emerald-500',
                )}
              />
              <span className="text-foreground">{p.name}</span>
              {p.start_year && (
                <span>
                  {p.start_year}
                  {p.end_year && p.end_year !== p.start_year ? `–${p.end_year}` : ''}
                </span>
              )}
              <span>{p.status}</span>
            </div>
          ))}
          {program.projects.length === 0 && <span className="text-xs">No iterations</span>}
        </div>
      )}
    </div>
  );
}
