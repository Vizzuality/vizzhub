import { useState } from 'react';
import { Globe, Pencil } from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Separator } from '@/shared/components/ui/separator';
import { useUpdateProgramProfile } from '../hooks/usePrograms';
import { ProgramNarrative } from './ProgramNarrative';
import { ProgramIterations } from './ProgramIterations';
import { ProgramTagsSection } from './ProgramTagsSection';
import { ProgramEditForm } from './ProgramEditForm';
import type { ProgramSummary } from '../types/portfolio';

/**
 * Full program view (header controls + tags + narrative + iterations) with
 * inline edit mode. Shared by the portfolio admin page and the project hub
 * Portfolio facet.
 */
export function ProgramPanel({
  program,
  leading,
  titleClassName = 'text-2xl',
}: {
  readonly program: ProgramSummary;
  /** Optional node before the title (e.g. a back button). */
  readonly leading?: React.ReactNode;
  readonly titleClassName?: string;
}): JSX.Element {
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const updateProfile = useUpdateProgramProfile(program.id);
  const [editing, setEditing] = useState(false);

  const subtitle = [
    program.profile?.stage,
    program.clients.map((c) => c.name).join(', ') || null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-2">
          {leading}
          <div className="min-w-0">
            <h2 className={cn('truncate font-semibold leading-tight', titleClassName)}>
              {program.name}
            </h2>
            {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Globe className="h-4 w-4" />
            {canManage ? (
              <>
                <span>On website</span>
                <Switch
                  checked={program.profile?.on_website ?? false}
                  onCheckedChange={(checked) =>
                    void updateProfile.mutateAsync({ on_website: checked })
                  }
                />
              </>
            ) : (
              <span>{program.profile?.on_website ? 'On website' : 'Not on website'}</span>
            )}
          </div>
          {canManage && !editing && (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="mr-2 h-3.5 w-3.5" /> Edit portfolio content
            </Button>
          )}
        </div>
      </div>

      {editing ? (
        <ProgramEditForm program={program} onDone={() => setEditing(false)} />
      ) : (
        <>
          <ProgramTagsSection program={program} />
          <Separator />
          <ProgramNarrative profile={program.profile} />
        </>
      )}

      <Separator />
      <ProgramIterations
        projects={program.projects}
        canManage={canManage}
        programId={program.id}
      />
    </div>
  );
}
