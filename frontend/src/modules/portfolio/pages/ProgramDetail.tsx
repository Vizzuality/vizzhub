import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useProgramDetail } from '../hooks/usePrograms';
import { ProgramPanel } from '../components/ProgramPanel';

export default function ProgramDetail(): JSX.Element {
  const { programId = '' } = useParams();
  const navigate = useNavigate();
  const { data: program, isLoading, isError } = useProgramDetail(programId);

  if (isLoading) return <LoadingSpinner />;
  if (isError || !program) {
    return (
      <div className="space-y-2 py-8 text-center">
        <p className="text-sm text-muted-foreground">Program not found.</p>
        <Button variant="outline" size="sm" onClick={() => navigate('/portfolio')}>
          Back to programs
        </Button>
      </div>
    );
  }

  return (
    <ProgramPanel
      program={program}
      leading={
        <Button
          variant="ghost"
          size="icon"
          className="mt-0.5 shrink-0"
          aria-label="Back to programs"
          onClick={() => navigate('/portfolio')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
      }
    />
  );
}
