import { useState } from 'react';
import { Pencil, Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { usePeriodsList, useCurrentPeriod } from '@/modules/accrual/hooks/usePeriods';
import { PeriodEditor } from '@/modules/accrual/components/PeriodEditor';
import type { AccrualPeriod } from '@/modules/accrual/types/accrual';

type EditorState =
  | { open: false }
  | { open: true; mode: 'create' }
  | { open: true; mode: 'edit'; period: AccrualPeriod };

export function Periods(): JSX.Element {
  const { data: periods = [], isLoading } = usePeriodsList();
  const { data: currentPeriod = null } = useCurrentPeriod();
  const [editor, setEditor] = useState<EditorState>({ open: false });

  // TODO Slice 2: derive from active Projects. For now, an empty list keeps
  // PeriodEditor functional — no "missing currency" warnings show until we
  // wire this in.
  const usedCurrencies: string[] = [];

  const close = (): void => setEditor({ open: false });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual periods</h1>
        <Button onClick={() => setEditor({ open: true, mode: 'create' })}>
          <Plus className="w-4 h-4 mr-2" />
          New period
        </Button>
      </div>
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2">Start date</th>
              <th>Status</th>
              <th>Closed at</th>
              <th>Currencies</th>
              <th className="w-px" />
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.id} className="border-b">
                <td className="py-2 font-mono">{p.start_date}</td>
                <td>{p.status}</td>
                <td className="text-muted-foreground">
                  {p.closed_at ? new Date(p.closed_at).toLocaleString() : '—'}
                </td>
                <td className="text-muted-foreground">
                  {Object.keys(p.fx_rates).sort().join(', ') || '—'}
                </td>
                <td>
                  {p.status === 'open' && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditor({ open: true, mode: 'edit', period: p })}
                    >
                      <Pencil className="w-3.5 h-3.5 mr-1" /> Edit currencies
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editor.open && (
        <PeriodEditor
          open
          mode={editor.mode}
          onClose={close}
          previousPeriod={editor.mode === 'edit' ? editor.period : currentPeriod}
          usedCurrencies={usedCurrencies}
        />
      )}
    </div>
  );
}
