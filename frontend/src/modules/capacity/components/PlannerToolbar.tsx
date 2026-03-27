import { ChevronLeft, ChevronRight, HelpCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
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
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground">
              <HelpCircle className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-64 text-sm" align="start">
            <p className="mb-2 font-medium">Keyboard shortcuts</p>
            <ul className="space-y-1 text-xs text-muted-foreground">
              <li><kbd className="rounded bg-muted px-1">Double-click</kbd> Edit cell</li>
              <li><kbd className="rounded bg-muted px-1">Click</kbd> Select cell</li>
              <li><kbd className="rounded bg-muted px-1">Shift+Click</kbd> Select range</li>
              <li><kbd className="rounded bg-muted px-1">Drag</kbd> Select range</li>
              <li><kbd className="rounded bg-muted px-1">Delete</kbd> Clear selected</li>
              <li><kbd className="rounded bg-muted px-1">0-9</kbd> Set value on selection</li>
              <li><kbd className="rounded bg-muted px-1">Ctrl+C</kbd> Copy cell value</li>
              <li><kbd className="rounded bg-muted px-1">Ctrl+V</kbd> Paste to selection</li>
              <li><kbd className="rounded bg-muted px-1">Esc</kbd> Clear selection</li>
            </ul>
          </PopoverContent>
        </Popover>
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
