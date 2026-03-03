import { Pencil, CheckCircle2, AlertCircle, Clock, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/lib/utils';
import MilestonesForm from '@/modules/scorecard/components/Forms/MilestonesForm';
import type { Milestone } from '@/modules/scorecard/types';

type MilestoneStatus = 'on-time' | 'late' | 'pending';

function getMilestoneActualDateColorClass(hasActualDate: boolean, status: MilestoneStatus): string {
  if (hasActualDate) {
    return status === 'on-time' ? 'text-score-green' : 'text-score-red';
  }
  return status === 'pending' ? 'text-score-green' : 'text-score-red';
}

interface MilestonesListProps {
  milestones: Milestone[] | null | undefined;
  isEditing: boolean;
  isLoading: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSubmit: (data: Milestone[]) => Promise<void>;
  onDelete: (index: number) => Promise<void>;
  getMilestoneStatus: (milestone: Milestone) => MilestoneStatus;
  onDirtyChange?: (isDirty: boolean) => void;
  onValuesChange?: (data: Milestone[]) => void;
}

export default function MilestonesList({
  milestones,
  isEditing,
  isLoading,
  onEdit,
  onCancelEdit,
  onSubmit,
  onDelete,
  getMilestoneStatus,
  onDirtyChange,
  onValuesChange,
}: MilestonesListProps): JSX.Element {
  if (isEditing) {
    return (
      <MilestonesForm
        initialData={milestones ?? undefined}
        onSubmit={onSubmit}
        onCancel={onCancelEdit}
        isLoading={isLoading}
        onDirtyChange={onDirtyChange}
        onValuesChange={onValuesChange}
      />
    );
  }

  return (
    <>
      {milestones && milestones.length > 0 ? (
        <div className="space-y-2">
          {milestones.map((milestone, index) => {
            const status = getMilestoneStatus(milestone);
            const milestoneKey = `${milestone.name}-${milestone.planned_date}`;
            return (
              <div
                key={milestoneKey}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg group"
              >
                <div className="flex items-center gap-3">
                  {status === 'on-time' && (
                    <CheckCircle2 className="w-5 h-5 text-score-green" />
                  )}
                  {status === 'late' && (
                    <AlertCircle className="w-5 h-5 text-score-red" />
                  )}
                  {status === 'pending' && (
                    <Clock className="w-5 h-5 text-muted-foreground" />
                  )}
                  <span className="font-medium">{milestone.name}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted-foreground">
                    Planned:{' '}
                    {new Date(milestone.planned_date).toLocaleDateString()}
                  </span>
                  <span
                    className={cn(
                      getMilestoneActualDateColorClass(!!milestone.actual_date, status)
                    )}
                  >
                    Actual:{' '}
                    {milestone.actual_date
                      ? new Date(milestone.actual_date).toLocaleDateString()
                      : '--/--/----'}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(index)}
                    disabled={isLoading}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-muted-foreground">No milestones defined yet.</p>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={onEdit}
        className="mt-4 border border-input"
      >
        <Pencil className="w-4 h-4 mr-2" />
        {milestones?.length ? 'Edit Milestones' : 'Add Milestones'}
      </Button>
    </>
  );
}
