import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FA_ORDER } from '@/modules/capacity/utils/constants';
import { PlannerSaveIndicator } from '@/modules/capacity/components/PlannerSaveIndicator';

interface PlannerToolbarProps {
  readonly groupBy: string;
  readonly onGroupByChange: (value: string) => void;
  readonly fa: string;
  readonly onFaChange: (value: string) => void;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly isSaving: boolean;
  readonly pendingCount: number;
}

export function PlannerToolbar({
  groupBy,
  onGroupByChange,
  fa,
  onFaChange,
  onPrev,
  onNext,
  isSaving,
  pendingCount,
}: PlannerToolbarProps): JSX.Element {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Capacity Planner</h1>
        <PlannerSaveIndicator isSaving={isSaving} pendingCount={pendingCount} />
      </div>
      <div className="flex items-center gap-2">
        <Select value={fa} onValueChange={onFaChange}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All FAs</SelectItem>
            {FA_ORDER.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={groupBy} onValueChange={onGroupByChange}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="project">By Project</SelectItem>
            <SelectItem value="user">By Person</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="icon" onClick={onPrev}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={onNext}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
