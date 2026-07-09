import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Globe, Pencil } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Separator } from '@/shared/components/ui/separator';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useProgramDetail, useUpdateProgramProfile } from '../hooks/usePrograms';
import { ProgramNarrative } from '../components/ProgramNarrative';
import { ProgramIterations } from '../components/ProgramIterations';
import { ProgramTagsSection } from '../components/ProgramTagsSection';
import { ProgramEditForm } from '../components/ProgramEditForm';

export default function ProgramDetail(): JSX.Element {
  const { programId = '' } = useParams();
  const navigate = useNavigate();
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const { data: program, isLoading, isError } = useProgramDetail(programId);
  const updateProfile = useUpdateProgramProfile(programId);
  const [editing, setEditing] = useState(false);

  if (isLoading) return <LoadingSpinner />;
  if (isError || !program) {
    return (
      <div className="space-y-2 py-8 text-center">
        <p className="text-sm text-muted-foreground">Program not found.</p>
        <Button variant="outline" size="sm" onClick={() => navigate('/admin/portfolio')}>
          Back to programs
        </Button>
      </div>
    );
  }

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
          <Button
            variant="ghost"
            size="icon"
            className="mt-0.5 shrink-0"
            aria-label="Back to programs"
            onClick={() => navigate('/admin/portfolio')}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold leading-tight">{program.name}</h1>
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
              <Pencil className="mr-2 h-3.5 w-3.5" /> Edit
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
        programId={programId}
      />
    </div>
  );
}
