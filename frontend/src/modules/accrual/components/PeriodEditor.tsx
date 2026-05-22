import { useState, useMemo } from 'react';
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
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { useCreatePeriod } from '@/modules/accrual/hooks/usePeriods';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

interface PeriodEditorProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly previousPeriod: AccrualPeriod | null;
  readonly usedCurrencies: readonly string[];
}

function firstOfCurrentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

interface RateRow {
  currency: string;
  rate: string;
  source: 'copied' | 'edited' | 'new';
}

export function PeriodEditor({
  open,
  onClose,
  previousPeriod,
  usedCurrencies,
}: PeriodEditorProps): JSX.Element {
  const [startDate, setStartDate] = useState(firstOfCurrentMonth());

  const initialRows = useMemo<RateRow[]>(() => {
    const copied: RateRow[] = previousPeriod
      ? Object.entries(previousPeriod.fx_rates).map(([currency, rate]) => ({
          currency,
          rate,
          source: 'copied' as const,
        }))
      : [];
    const known = new Set(copied.map((r) => r.currency));
    const missing: RateRow[] = usedCurrencies
      .filter((c) => c !== 'EUR' && !known.has(c))
      .map((currency) => ({ currency, rate: '', source: 'new' as const }));
    return [...copied, ...missing];
  }, [previousPeriod, usedCurrencies]);

  const [rows, setRows] = useState<RateRow[]>(initialRows);
  const [newCurrency, setNewCurrency] = useState('');
  const [newRate, setNewRate] = useState('');
  const [addError, setAddError] = useState<string | null>(null);

  const create = useCreatePeriod();

  const updateRow = (currency: string, rate: string): void => {
    setRows((prev) =>
      prev.map((r) =>
        r.currency === currency ? { ...r, rate, source: 'edited' as const } : r,
      ),
    );
  };

  const removeRow = (currency: string): void => {
    setRows((prev) => prev.filter((r) => r.currency !== currency));
  };

  const addRow = (): void => {
    const code = newCurrency.trim().toUpperCase();
    if (code.length !== 3 || !/^[A-Z]{3}$/.test(code)) {
      setAddError('Currency must be a 3-letter ISO code (e.g. USD).');
      return;
    }
    if (code === 'EUR') {
      setAddError('EUR is the base currency — no rate needed.');
      return;
    }
    if (rows.some((r) => r.currency === code)) {
      setAddError(`${code} is already in the list.`);
      return;
    }
    setRows((prev) => [...prev, { currency: code, rate: newRate.trim(), source: 'new' }]);
    setNewCurrency('');
    setNewRate('');
    setAddError(null);
  };

  const missingRates = rows.filter((r) => !r.rate.trim());

  const handleSubmit = async (): Promise<void> => {
    const fx_rates = Object.fromEntries(
      rows.filter((r) => r.rate.trim()).map((r) => [r.currency, r.rate.trim()]),
    );
    await create.mutateAsync({ start_date: startDate, fx_rates });
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Open new accrual period</DialogTitle>
          <DialogDescription>
            Set the start date and FX rates for the new accrual period. Any currency left without a
            manual rate will use the European Central Bank daily rate at save time.
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
          <div>
            <Label>FX rates</Label>
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="pb-2">Currency</th>
                  <th className="pb-2">Rate (per 1 EUR)</th>
                  <th className="pb-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.currency}>
                    <td className="py-1 font-mono">{r.currency}</td>
                    <td className="py-1">
                      <Input
                        aria-label={`FX rate for ${r.currency}`}
                        value={r.rate}
                        onChange={(e) => updateRow(r.currency, e.target.value)}
                        placeholder="e.g. 1.10"
                      />
                    </td>
                    <td className="py-1 text-xs text-muted-foreground">
                      <div className="flex items-center justify-between gap-2">
                        <span>
                          {r.source === 'copied' && 'copied from previous'}
                          {r.source === 'edited' && 'edited'}
                          {r.source === 'new' && 'new — needs rate'}
                        </span>
                        <button
                          type="button"
                          aria-label={`Remove ${r.currency}`}
                          onClick={() => removeRow(r.currency)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-3 text-xs text-muted-foreground italic">
                      No currencies yet — add at least one below (USD is typical).
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="mt-3 flex items-end gap-2">
              <div className="flex-1">
                <Label htmlFor="new_currency" className="text-xs">Add currency</Label>
                <Input
                  id="new_currency"
                  value={newCurrency}
                  onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
                  placeholder="USD"
                  maxLength={3}
                  className="font-mono"
                />
              </div>
              <div className="flex-1">
                <Label htmlFor="new_rate" className="text-xs">Rate (per 1 EUR)</Label>
                <Input
                  id="new_rate"
                  value={newRate}
                  onChange={(e) => setNewRate(e.target.value)}
                  placeholder="1.10"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRow(); } }}
                />
              </div>
              <Button type="button" variant="outline" onClick={addRow}>
                <Plus className="w-4 h-4 mr-1" /> Add
              </Button>
            </div>
            {addError && (
              <p className="mt-1 text-xs text-destructive" role="alert">{addError}</p>
            )}
          </div>
          {missingRates.length > 0 && (
            <div className="flex items-start gap-2 text-amber-600 text-sm">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
              <span>
                {missingRates.length} {missingRates.length === 1 ? 'currency has' : 'currencies have'} no
                rate — projects in those currencies will fall back to ECB.
              </span>
            </div>
          )}
          {previousPeriod && (
            <p className="text-sm text-muted-foreground">
              This will close the current open period and freeze its cells.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={create.isPending}>
            {create.isPending ? 'Opening…' : 'Open period'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
