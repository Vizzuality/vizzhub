import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { usePeriodsList, useCurrentPeriod } from '@/modules/accrual/hooks/usePeriods';
import { PeriodEditor } from '@/modules/accrual/components/PeriodEditor';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

/** The CEO's rates are the source of truth; ECB usd_rate is shown only as a fallback. */
function PeriodRates({ period }: { readonly period: AccrualPeriod }): JSX.Element {
  const entries = Object.entries(period.fx_rates ?? {});
  if (entries.length > 0) {
    return (
      <span className="tabular-nums">
        {entries
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([cur, rate]) => `${cur} ${Number(rate).toFixed(4)}`)
          .join(' · ')}
      </span>
    );
  }
  if (period.usd_rate) {
    return (
      <span className="tabular-nums text-muted-foreground" title="ECB fallback — no CEO rate set">
        USD {Number(period.usd_rate).toFixed(4)} <span className="text-[10px]">ECB</span>
      </span>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}

export function Periods(): JSX.Element {
  const { data: periods = [], isLoading } = usePeriodsList();
  const { data: currentPeriod = null } = useCurrentPeriod();
  const [editorOpen, setEditorOpen] = useState(false);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual periods</h1>
        <Button onClick={() => setEditorOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          New period
        </Button>
      </div>
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <table className="w-full text-sm [&_th]:px-3 [&_td]:px-3 [&_th:first-child]:pl-0 [&_td:first-child]:pl-0 [&_th:last-child]:pr-0 [&_td:last-child]:pr-0">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2">Start date</th>
              <th>Status</th>
              <th className="text-right">FX rate (per €)</th>
              <th>Closed at</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.id} className="border-b">
                <td className="py-2 font-mono">{p.start_date}</td>
                <td>{p.status}</td>
                <td className="text-right">
                  <PeriodRates period={p} />
                </td>
                <td className="text-muted-foreground">
                  {p.closed_at ? new Date(p.closed_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editorOpen && (
        <PeriodEditor
          open
          onClose={() => setEditorOpen(false)}
          previousPeriod={currentPeriod}
        />
      )}
    </div>
  );
}
