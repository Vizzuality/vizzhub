import { useProjectContext } from '@/core/contexts/ProjectContext';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useProgramDetail } from '../hooks/usePrograms';
import { ProgramPanel } from '../components/ProgramPanel';

/** Project hub facet: the full program view, embedded under the project header. */
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

  return <ProgramPanel program={program} titleClassName="text-lg" />;
}
