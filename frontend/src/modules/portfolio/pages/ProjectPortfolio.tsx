import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { useProjectContext } from '@/core/contexts/ProjectContext';
import { Button } from '@/shared/components/ui/button';
import { Separator } from '@/shared/components/ui/separator';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useProgramDetail } from '../hooks/usePrograms';
import { ProgramTagsSection } from '../components/ProgramTagsSection';
import { ProgramNarrative } from '../components/ProgramNarrative';
import { ProgramIterations } from '../components/ProgramIterations';

/** Project hub facet: read-only portfolio view of the project's program. */
export default function ProjectPortfolio(): JSX.Element {
  const { project } = useProjectContext();
  const programId = project.program_id ?? undefined;
  const { data: program, isLoading } = useProgramDetail(programId);

  if (!programId) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        This project is not assigned to any program.
      </p>
    );
  }
  if (isLoading) return <LoadingSpinner />;
  if (!program) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">Program not found.</p>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold leading-tight">{program.name}</h2>
          {program.profile?.stage && (
            <p className="mt-0.5 text-sm text-muted-foreground">{program.profile.stage}</p>
          )}
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to={`/admin/portfolio/programs/${program.id}`}>
            <ExternalLink className="mr-2 h-3.5 w-3.5" /> Open in Portfolio
          </Link>
        </Button>
      </div>

      <ProgramTagsSection program={program} />
      <Separator />
      <ProgramNarrative profile={program.profile} />
      <Separator />
      <ProgramIterations projects={program.projects} canManage={false} programId={program.id} />
    </div>
  );
}
