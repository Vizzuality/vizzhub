import { useState } from 'react';
import { Plus, X } from 'lucide-react';
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
import { useCreatePeriod, useUpdatePeriod } from '@/modules/accrual/hooks/usePeriods';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

interface PeriodEditorProps {
  readonly open: boolean;
  readonly onClose: () => void;
  /** Carries the open period (create mode prefills its rates as a starting point). */
  readonly previousPeriod: AccrualPeriod | null;
  /** When set, the editor edits this period's fx_rates instead of creating one. */
  readonly period?: AccrualPeriod | null;
}

interface RateRow {
  currency: string;
  rate: string;
}

function firstOfCurrentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function ratesToRows(fx: Record<string, string> | undefined): RateRow[] {
  return Object.entries(fx ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, rate]) => ({ currency, rate }));
}

function rowsToRates(rows: RateRow[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { currency, rate } of rows) {
    const code = currency.trim().toUpperCase();
    if (code && rate.trim()) out[code] = rate.trim();
  }
  return out;
}

export function PeriodEditor({
  open,
  onClose,
  previousPeriod,
  period = null,
}: PeriodEditorProps): JSX.Element {
  const isEdit = period !== null;
  const [startDate, setStartDate] = useState(firstOfCurrentMonth());
  const [rows, setRows] = useState<RateRow[]>(
    ratesToRows(period?.fx_rates ?? previousPeriod?.fx_rates),
  );
  const create = useCreatePeriod();
  const update = useUpdatePeriod();
  const pending = create.isPending || update.isPending;

  const setRow = (i: number, patch: Partial<RateRow>): void =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = (): void => setRows((rs) => [...rs, { currency: '', rate: '' }]);
  const removeRow = (i: number): void => setRows((rs) => rs.filter((_, idx) => idx !== i));

  const handleSubmit = async (): Promise<void> => {
    const fx_rates = rowsToRates(rows);
    if (isEdit && period) {
      await update.mutateAsync({ id: period.id, payload: { fx_rates } });
    } else {
      await create.mutateAsync({ start_date: startDate, fx_rates });
    }
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit period FX rates' : 'Open new accrual period'}</DialogTitle>
          <DialogDescription>
            The per-currency rate (units of foreign currency per €) is the source of truth for
            conversion this period; ECB is used only as a fallback.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {isEdit ? (
            <div>
              <Label>Period</Label>
              <p className="text-sm font-mono">{period?.start_date}</p>
            </div>
          ) : (
            <div>
              <Label htmlFor="period_start_date">Start date</Label>
              <Input
                id="period_start_date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label>FX rates (per €)</Label>
            {rows.length === 0 && (
              <p className="text-sm text-muted-foreground">No rates yet — ECB fallback applies.</p>
            )}
            {rows.map((row, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  aria-label={`Currency ${i + 1}`}
                  className="w-24 uppercase"
                  placeholder="USD"
                  maxLength={3}
                  value={row.currency}
                  onChange={(e) => setRow(i, { currency: e.target.value })}
                />
                <Input
                  aria-label={`Rate ${i + 1}`}
                  className="flex-1 tabular-nums"
                  placeholder="1.08"
                  inputMode="decimal"
                  value={row.rate}
                  onChange={(e) => setRow(i, { rate: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove row ${i + 1}`}
                  onClick={() => removeRow(i)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addRow}>
              <Plus className="h-4 w-4 mr-1" />
              Add currency
            </Button>
          </div>

          {!isEdit && previousPeriod && (
            <p className="text-sm text-muted-foreground">
              This will close the current open period and freeze its cells.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={pending}>
            {pending ? 'Saving…' : isEdit ? 'Save rates' : 'Open period'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
