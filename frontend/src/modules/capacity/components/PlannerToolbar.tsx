import { ChevronLeft, ChevronRight, HelpCircle } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FA_ORDER } from '@/modules/capacity/utils/constants';
import { getPlannerCellColors } from '@/modules/capacity/utils/plannerColors';
import { PlannerSaveIndicator } from '@/modules/capacity/components/PlannerSaveIndicator';

interface LegendItem {
  readonly sample: number;
  readonly label: string;
  readonly range: string;
}

const LEGEND_ITEMS: LegendItem[] = [
  { sample: 10, label: 'Less than 1 day per week', range: '1 → 20%' },
  { sample: 30, label: 'More than 1 day, less than 2 days per week', range: '21 → 40%' },
  { sample: 50, label: 'More than 2 days, less than 3 days per week', range: '41 → 60%' },
  { sample: 70, label: 'More than 3 days, less than 4 days per week', range: '61 → 80%' },
  { sample: 90, label: 'More than 4 days, less than 5 days per week', range: '81 → 100%' },
  { sample: 150, label: 'More than 5 days per week (over-allocated)', range: '> 100%' },
];

const SHORTCUTS: readonly { readonly keys: string; readonly desc: string }[] = [
  { keys: 'Double-click', desc: 'Edit cell' },
  { keys: 'Click', desc: 'Select cell' },
  { keys: 'Shift+Click', desc: 'Select range' },
  { keys: 'Drag', desc: 'Select range' },
  { keys: 'Delete', desc: 'Clear selected' },
  { keys: '0-9', desc: 'Set value on selection' },
  { keys: 'Ctrl+C', desc: 'Copy cell value' },
  { keys: 'Ctrl+V', desc: 'Paste to selection' },
  { keys: 'Esc', desc: 'Clear selection' },
];

function LegendSwatch({ sample, isDark }: { readonly sample: number; readonly isDark: boolean }): JSX.Element {
  const colors = getPlannerCellColors(sample, isDark);
  return (
    <span
      className="inline-block h-4 w-6 rounded-sm border"
      style={{ backgroundColor: colors?.bg }}
    />
  );
}

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
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Capacity Planner</h1>
        <PlannerSaveIndicator isSaving={isSaving} pendingCount={pendingCount} />
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground">
              <HelpCircle className="h-4 w-4" />
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Capacity Planner — Help</DialogTitle>
            </DialogHeader>
            <div className="space-y-6 text-sm">
              <section>
                <h3 className="mb-2 font-medium">Instructions</h3>
                <ul className="list-disc space-y-1.5 pl-5 text-muted-foreground">
                  <li>Think the number of <span className="font-medium text-foreground">hours</span> you are expected to work on a given project during a given <span className="font-medium text-foreground">week</span>.</li>
                  <li>Translate to a percentage, taking into account 100% is your full week. (If you are working 40 hours/week, 8 hours are equivalent to 20%).</li>
                  <li>The input allows integers from 1 to 200.</li>
                  <li>Input the number in the cell (decimals are not allowed).</li>
                  <li>Remember this is an estimate, so things might change.</li>
                  <li>Fill this in or review it at least once a month, and ideally every time there is a change in your capacity assessment.</li>
                </ul>
              </section>

              <section>
                <h3 className="mb-2 font-medium">Legend</h3>
                <ul className="space-y-1">
                  {LEGEND_ITEMS.map((item) => (
                    <li key={item.sample} className="flex items-center gap-3 text-muted-foreground">
                      <LegendSwatch sample={item.sample} isDark={isDark} />
                      <span className="flex-1">{item.label}</span>
                      <span className="font-medium text-foreground tabular-nums">{item.range}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h3 className="mb-2 font-medium">Keyboard shortcuts</h3>
                <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-muted-foreground">
                  {SHORTCUTS.map((s) => (
                    <li key={s.keys} className="flex items-center gap-2">
                      <kbd className="rounded bg-muted px-1.5 py-0.5 font-mono">{s.keys}</kbd>
                      <span>{s.desc}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </DialogContent>
        </Dialog>
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
