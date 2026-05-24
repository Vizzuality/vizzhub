import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useCreatePeriod } from '@/modules/accrual/hooks/usePeriods';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

interface PeriodEditorProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly previousPeriod: AccrualPeriod | null;
}

function firstOfCurrentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

export function PeriodEditor({
  open,
  onClose,
  previousPeriod,
}: PeriodEditorProps): JSX.Element {
  const [startDate, setStartDate] = useState(firstOfCurrentMonth());
  const create = useCreatePeriod();

  const handleSubmit = async (): Promise<void> => {
    await create.mutateAsync({ start_date: startDate });
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Open new accrual period</DialogTitle>
          <DialogDescription>
            Pick the start date of the new accounting period. Cells already in EUR are frozen at close — no FX rates needed.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="period_start_date">Start date</Label>
            <Input
              id="period_start_date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          {previousPeriod && (
            <p className="text-sm text-muted-foreground">
              This will close the current open period and freeze its cells.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={create.isPending}>
            {create.isPending ? 'Opening…' : 'Open period'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
