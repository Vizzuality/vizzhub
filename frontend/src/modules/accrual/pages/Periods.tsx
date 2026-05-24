import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { usePeriodsList, useCurrentPeriod } from '@/modules/accrual/hooks/usePeriods';
import { PeriodEditor } from '@/modules/accrual/components/PeriodEditor';

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
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2">Start date</th>
              <th>Status</th>
              <th>Closed at</th>
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
