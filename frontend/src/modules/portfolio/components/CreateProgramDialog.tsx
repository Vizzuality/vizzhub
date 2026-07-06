import { Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

export function CreateProgramDialog(): JSX.Element {
  return (
    <Button size="sm" variant="outline" disabled>
      <Plus className="mr-1 h-3.5 w-3.5" />
      New program
    </Button>
  );
}
