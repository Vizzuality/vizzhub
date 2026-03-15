import { Link } from 'react-router-dom';
import { Pencil } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

interface StatusControlsProps {
  readonly projectId: string;
}

export default function StatusControls({ projectId }: StatusControlsProps): JSX.Element {
  return (
    <Button variant="ghost" size="sm" className="border border-input" asChild>
      <Link to={`/projects/${projectId}/edit`}>
        <Pencil className="w-4 h-4 mr-2" />
        Edit
      </Link>
    </Button>
  );
}
