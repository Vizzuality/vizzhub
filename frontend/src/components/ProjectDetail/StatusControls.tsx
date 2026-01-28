import { Link } from 'react-router-dom';
import { Flag, RotateCcw, Pencil, Trash2, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ProjectStatus } from '../../types';

interface StatusControlsProps {
  projectId: string;
  status: ProjectStatus;
  onMarkFinished: () => void;
  onReopen: () => Promise<unknown>;
  onEdit: () => void;
  onDelete: () => void;
  isUpdatingStatus: boolean;
}

export default function StatusControls({
  projectId,
  status,
  onMarkFinished,
  onReopen,
  onEdit,
  onDelete,
  isUpdatingStatus,
}: StatusControlsProps): JSX.Element {
  return (
    <div className="flex items-center gap-2">
      <Button variant="ghost" asChild className="border border-input">
        <Link to={`/projects/${projectId}/history`}>
          <TrendingUp className="w-5 h-5 mr-2" />
          History
        </Link>
      </Button>
      {status === 'in_progress' ? (
        <Button
          variant="ghost"
          onClick={onMarkFinished}
          className="border border-input text-score-green hover:bg-score-green hover:text-white dark:hover:text-black hover:border-score-green"
          disabled={isUpdatingStatus}
        >
          <Flag className="w-5 h-5 mr-2" />
          Mark as Finished
        </Button>
      ) : (
        <Button
          variant="ghost"
          onClick={onReopen}
          className="border border-input"
          disabled={isUpdatingStatus}
        >
          <RotateCcw className="w-5 h-5 mr-2" />
          Reopen Project
        </Button>
      )}
      <Button variant="ghost" onClick={onEdit} className="border border-input">
        <Pencil className="w-5 h-5 mr-2" />
        Edit
      </Button>
      <Button
        variant="ghost"
        onClick={onDelete}
        className="border border-input text-destructive hover:bg-destructive hover:text-destructive-foreground"
      >
        <Trash2 className="w-5 h-5 mr-2" />
        Delete
      </Button>
    </div>
  );
}
