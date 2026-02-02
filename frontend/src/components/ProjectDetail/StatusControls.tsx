import { Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface StatusControlsProps {
  readonly onEdit: () => void;
}

export default function StatusControls({
  onEdit,
}: StatusControlsProps): JSX.Element {
  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-2">
        <Button variant="ghost" onClick={onEdit} className="border border-input">
          <Pencil className="w-5 h-5 mr-2" />
          Edit
        </Button>
      </div>
    </div>
  );
}
