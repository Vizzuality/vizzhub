import { Link } from 'react-router-dom';
import { Globe } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { TermChips } from './TermChips';
import { iterationSummary } from '../utils/programs';
import type { ProgramSummary } from '../types/portfolio';

export function ProgramCard({ program }: { readonly program: ProgramSummary }): JSX.Element {
  return (
    <Link to={`/portfolio/programs/${program.id}`} className="block">
      <Card className="h-full transition-colors hover:bg-accent/50">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <span className="truncate">{program.name}</span>
            {program.profile?.on_website && (
              <Globe className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
          </CardTitle>
          <div className="text-xs text-muted-foreground">
            {[
              program.clients.map((c) => c.name).join(', '),
              program.profile?.stage ?? undefined,
            ]
              .filter(Boolean)
              .join(' · ')}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          <TermChips terms={program.terms} />
          {program.profile?.short_description && (
            <p className="line-clamp-2 text-sm text-muted-foreground">
              {program.profile.short_description}
            </p>
          )}
          <p className="text-xs text-muted-foreground">{iterationSummary(program.projects)}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
