import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import InfoTooltip from './InfoTooltip';
import type { Milestone } from '@/types';

interface MilestonesCardProps {
  milestones: Milestone[] | null | undefined;
  onTimeMilestones: number | null;
  milestonesTarget: number;
  isExpanded: boolean;
  onToggle: () => void;
}

export default function MilestonesCard({
  milestones,
  onTimeMilestones,
  milestonesTarget,
  isExpanded,
  onToggle,
}: MilestonesCardProps): JSX.Element {
  const milestonesTargetPct = milestonesTarget * 100;

  return (
    <button
      onClick={onToggle}
      className="p-4 bg-muted/50 rounded-lg border text-left hover:bg-muted/70 transition-colors"
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">On-Time Milestones</p>
          <InfoTooltip>
            <p className="text-sm">On-time delivery rate</p>
            <p className="text-xs text-white/70 mt-1">Target: {milestonesTargetPct.toFixed(0)}%</p>
          </InfoTooltip>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </div>
      {onTimeMilestones !== null ? (
        <>
          <p
            className={cn(
              'text-xl font-semibold',
              onTimeMilestones >= milestonesTarget
                ? 'text-score-green'
                : onTimeMilestones >= milestonesTarget * 0.9
                ? 'text-score-yellow'
                : 'text-score-red'
            )}
          >
            {(onTimeMilestones * 100).toFixed(0)}%
          </p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">
              {milestones?.length || 0} milestone
              {(milestones?.length || 0) !== 1 ? 's' : ''}
            </p>
            <p className="text-xs text-chart-3">expand to edit</p>
          </div>
        </>
      ) : (
        <>
          <p className="text-xl font-semibold text-muted-foreground">&mdash;</p>
          <div className="flex justify-between items-center">
            <p className="text-xs text-muted-foreground">No milestones</p>
            <p className="text-xs text-chart-3">expand to edit</p>
          </div>
        </>
      )}
    </button>
  );
}
