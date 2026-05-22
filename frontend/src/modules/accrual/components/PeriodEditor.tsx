import { useState, useMemo, useEffect } from 'react';
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
import {
  useCreatePeriod,
  usePatchPeriod,
  useSeedRates,
} from '@/modules/accrual/hooks/usePeriods';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

/**
 * Currencies always visible by default. Others can be added on demand from
 * the dropdown below the table (which lists every code with an ECB rate).
 */
const MAJOR_CURRENCIES = ['USD', 'GBP', 'CAD', 'CHF'] as const;

interface PeriodEditorProps {
  readonly open: boolean;
  readonly onClose: () => void;
  /**
   * - `'create'` (default): opens a new period; closes the current open one
   *   and freezes its cells.
   * - `'edit'`: patches `fx_rates` of the period passed as `previousPeriod`.
   *   No freeze, no `start_date` change.
   */
  readonly mode?: 'create' | 'edit';
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
  source: 'copied' | 'ecb' | 'edited' | 'new';
}

export function PeriodEditor({
  open,
  onClose,
  mode = 'create',
  previousPeriod,
  usedCurrencies,
}: PeriodEditorProps): JSX.Element {
  const isEdit = mode === 'edit';
  const [startDate, setStartDate] = useState(firstOfCurrentMonth());

  const { data: seedRates } = useSeedRates(open);

  const initialRows = useMemo<RateRow[]>(() => {
    // Start with the union of: previous period's locked currencies, the
    // major-currency whitelist, and any currency in active use by Projects.
    // For each, pre-fill the rate from (in order): previous period → ECB seed → empty.
    const seen = new Set<string>();
    const built: RateRow[] = [];
    const prevRates = previousPeriod?.fx_rates ?? {};

    const candidates = [
      ...Object.keys(prevRates),
      ...MAJOR_CURRENCIES,
      ...usedCurrencies,
    ];

    for (const raw of candidates) {
      const code = raw.toUpperCase();
      if (code === 'EUR' || seen.has(code)) continue;
      seen.add(code);

      const fromPrev = prevRates[code];
      const fromEcb = seedRates?.[code];
      if (fromPrev) {
        built.push({ currency: code, rate: fromPrev, source: 'copied' });
      } else if (fromEcb) {
        built.push({ currency: code, rate: fromEcb, source: 'ecb' });
      } else {
        built.push({ currency: code, rate: '', source: 'new' });
      }
    }
    return built.sort((a, b) => a.currency.localeCompare(b.currency));
  }, [previousPeriod, usedCurrencies, seedRates]);

  const [rows, setRows] = useState<RateRow[]>(initialRows);

  // Re-seed the rows whenever the inputs change (e.g. seedRates loads after mount).
  useEffect(() => {
    setRows(initialRows);
  }, [initialRows]);

  const [pickerValue, setPickerValue] = useState('');

  const create = useCreatePeriod();
  const patch = usePatchPeriod();
  const submitting = create.isPending || patch.isPending;

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

  const addFromPicker = (code: string): void => {
    if (!code || code === 'EUR') return;
    if (rows.some((r) => r.currency === code)) return;
    const rate = seedRates?.[code] ?? '';
    const source: RateRow['source'] = rate ? 'ecb' : 'new';
    setRows((prev) =>
      [...prev, { currency: code, rate, source }].sort((a, b) =>
        a.currency.localeCompare(b.currency),
      ),
    );
    setPickerValue('');
  };

  const availableForPicker = useMemo(() => {
    const present = new Set(rows.map((r) => r.currency));
    return Object.keys(seedRates ?? {})
      .filter((c) => c !== 'EUR' && !present.has(c))
      .sort();
  }, [rows, seedRates]);

  const missingRates = rows.filter((r) => !r.rate.trim());

  const handleSubmit = async (): Promise<void> => {
    const fx_rates = Object.fromEntries(
      rows.filter((r) => r.rate.trim()).map((r) => [r.currency, r.rate.trim()]),
    );
    if (isEdit && previousPeriod) {
      await patch.mutateAsync({ id: previousPeriod.id, payload: { fx_rates } });
    } else {
      await create.mutateAsync({ start_date: startDate, fx_rates });
    }
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit period FX rates' : 'Open new accrual period'}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? 'Add or change the FX rates locked for this period. Past months are not affected.'
              : 'Set the start date and FX rates for the new accrual period. Any currency left without a manual rate will use the European Central Bank daily rate at save time.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {!isEdit && (
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
                          {r.source === 'copied' && 'from previous period'}
                          {r.source === 'ecb' && 'latest ECB rate'}
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
                      No currencies — pick one below to add.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {availableForPicker.length > 0 && (
              <div className="mt-3 flex items-end gap-2">
                <div className="flex-1">
                  <Label htmlFor="add_currency_picker" className="text-xs">
                    Add another currency
                  </Label>
                  <select
                    id="add_currency_picker"
                    value={pickerValue}
                    onChange={(e) => setPickerValue(e.target.value)}
                    className="w-full h-9 px-3 rounded-md border border-input bg-transparent text-sm font-mono"
                  >
                    <option value="">— select —</option>
                    {availableForPicker.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => addFromPicker(pickerValue)}
                  disabled={!pickerValue}
                >
                  <Plus className="w-4 h-4 mr-1" /> Add
                </Button>
              </div>
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
          {!isEdit && previousPeriod && (
            <p className="text-sm text-muted-foreground">
              This will close the current open period and freeze its cells.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting
              ? (isEdit ? 'Saving…' : 'Opening…')
              : (isEdit ? 'Save changes' : 'Open period')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
