import { Pencil, CheckCircle2, AlertCircle, Clock, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/lib/utils';
import MilestonesForm from '@/modules/scorecard/components/Forms/MilestonesForm';
import type { Milestone } from '@/modules/scorecard/types';

type MilestoneStatus = 'on-time' | 'late' | 'pending';

function getMilestoneDotClass(hasActualDate: boolean, status: MilestoneStatus): string {
  if (hasActualDate) {
    return status === 'on-time' ? 'bg-aux-neon-grass' : 'bg-aux-red';
  }
  return status === 'pending' ? 'bg-aux-neon-grass' : 'bg-aux-red';
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
  readOnly?: boolean;
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
  readOnly = false,
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
                    <CheckCircle2 className="w-5 h-5 text-aux-neon-grass" />
                  )}
                  {status === 'late' && (
                    <AlertCircle className="w-5 h-5 text-aux-red" />
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
                  <span className="flex items-center gap-1.5">
                    <span className={cn('inline-block w-1.5 h-1.5 rounded-full shrink-0', getMilestoneDotClass(!!milestone.actual_date, status))} />
                    Actual:{' '}
                    {milestone.actual_date
                      ? new Date(milestone.actual_date).toLocaleDateString()
                      : '--/--/----'}
                  </span>
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                      onClick={() => onDelete(index)}
                      disabled={isLoading}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-muted-foreground">No milestones defined yet.</p>
      )}
      {!readOnly && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onEdit}
          className="mt-4 border border-input"
        >
          <Pencil className="w-4 h-4 mr-2" />
          {milestones?.length ? 'Edit Milestones' : 'Add Milestones'}
        </Button>
      )}
    </>
  );
}
