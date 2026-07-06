import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Check, Globe, Pencil, X } from 'lucide-react';
import { getApiErrorMessage } from '@/utils/apiErrors';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Switch } from '@/shared/components/ui/switch';
import { Separator } from '@/shared/components/ui/separator';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  useProgramDetail,
  useRenameProgram,
  useUpdateProgramProfile,
} from '../hooks/usePrograms';
import { ProgramNarrative } from '../components/ProgramNarrative';
import { ProgramIterations } from '../components/ProgramIterations';
import { ProgramTagsSection } from '../components/ProgramTagsSection';

export default function ProgramDetail(): JSX.Element {
  const { programId = '' } = useParams();
  const navigate = useNavigate();
  const canManage = usePermission(Action.PORTFOLIO_MANAGE);
  const { data: program, isLoading, isError } = useProgramDetail(programId);
  const rename = useRenameProgram(programId);
  const updateProfile = useUpdateProgramProfile(programId);
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [renameError, setRenameError] = useState('');

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

  const handleRename = async (): Promise<void> => {
    setRenameError('');
    try {
      await rename.mutateAsync(nameDraft.trim());
      setRenaming(false);
    } catch (err) {
      setRenameError(
        getApiErrorMessage(err as Error, {
          conflict: 'A program with this name already exists',
          fallback: 'Could not rename the program',
        }),
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin/portfolio')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        {renaming ? (
          <div className="flex items-center gap-1">
            <Input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              className="h-8 w-64"
              autoFocus
            />
            <Button
              size="icon"
              variant="ghost"
              onClick={() => void handleRename()}
              disabled={!nameDraft.trim() || rename.isPending}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                setRenaming(false);
                setRenameError('');
              }}
            >
              <X className="h-4 w-4" />
            </Button>
            {renameError && <span className="text-sm text-destructive">{renameError}</span>}
          </div>
        ) : (
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            {program.name}
            {canManage && (
              <Button
                size="icon"
                variant="ghost"
                aria-label="Edit name"
                onClick={() => {
                  setNameDraft(program.name);
                  setRenaming(true);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
          </h1>
        )}
        {program.profile?.stage && (
          <span className="text-sm text-muted-foreground">{program.profile.stage}</span>
        )}
        <span className="text-sm text-muted-foreground">
          {program.clients.map((c) => c.name).join(', ')}
        </span>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <Globe className="h-4 w-4 text-muted-foreground" />
          {canManage ? (
            <Switch
              checked={program.profile?.on_website ?? false}
              onCheckedChange={(checked) =>
                void updateProfile.mutateAsync({ on_website: checked })
              }
            />
          ) : (
            <span className="text-muted-foreground">
              {program.profile?.on_website ? 'On website' : 'Not on website'}
            </span>
          )}
        </div>
      </div>

      <ProgramTagsSection program={program} canManage={canManage} />
      <Separator />
      <ProgramNarrative
        profile={program.profile}
        canManage={canManage}
        isSaving={updateProfile.isPending}
        onSave={async (diff) => {
          await updateProfile.mutateAsync(diff);
        }}
      />
      <Separator />
      <ProgramIterations
        projects={program.projects}
        canManage={canManage}
        programId={programId}
      />
    </div>
  );
}
