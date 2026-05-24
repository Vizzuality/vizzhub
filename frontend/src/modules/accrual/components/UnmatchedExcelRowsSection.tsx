import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { useUnmatchedExcelRows } from '@/modules/accrual/hooks/useUnmatched';
import { MapExcelRowDialog } from '@/modules/accrual/components/MapExcelRowDialog';
import type { AccrualExcelRow } from '@/modules/accrual/types/accrual';

const fmt = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function formatEur(value: string | null | undefined): string {
  if (!value) return '—';
  const n = Number.parseFloat(value);
  return Number.isNaN(n) ? value : fmt.format(n);
}

export function UnmatchedExcelRowsSection(): JSX.Element {
  const [search, setSearch] = useState('');
  const [target, setTarget] = useState<AccrualExcelRow | null>(null);
  const { data, isLoading, error } = useUnmatchedExcelRows(
    search ? { excel_code: search } : {},
  );

  return (
    <section className="space-y-3">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Excel rows without a tracker match</h2>
          <p className="text-sm text-muted-foreground">
            These Excel rows were not resolved to any tracker project in the latest import.
            Map each one to its project(s) or accept that it's not billable.
          </p>
        </div>
        <Input
          placeholder="Filter by code…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64"
        />
      </header>

      {error && <p className="text-sm text-destructive">Failed to load Excel rows.</p>}
      {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}

      {data && data.items.length === 0 && (
        <p className="rounded border border-dashed border-muted-foreground/30 bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
          No unmatched Excel rows in the latest import run.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Code</th>
                <th className="px-3 py-2 text-left font-medium">Name</th>
                <th className="px-3 py-2 text-left font-medium">PM</th>
                <th className="px-3 py-2 text-right font-medium">EUR</th>
                <th className="px-3 py-2 text-left font-medium">Period</th>
                <th className="px-3 py-2 text-left font-medium">Mapped to</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.items.map((row) => (
                <tr key={row.id} className="hover:bg-muted/20">
                  <td className="px-3 py-2 font-mono text-xs">{row.excel_code}</td>
                  <td className="px-3 py-2">{row.name ?? '—'}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{row.pm_name ?? '—'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatEur(row.value_eur)}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {row.start_date ?? '—'} → {row.end_date ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {row.alias_project_id ? (
                      <Link
                        to={`/tracker/projects/${row.alias_project_id}`}
                        className="hover:underline"
                        title={row.alias_project_code ?? undefined}
                      >
                        {row.alias_project_name}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      size="sm"
                      variant={row.alias_project_id ? 'ghost' : 'outline'}
                      onClick={() => setTarget(row)}
                    >
                      {row.alias_project_id ? 'Remap' : 'Map to project'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-3 py-2 text-xs text-muted-foreground">
            {data.total} unmatched row{data.total === 1 ? '' : 's'}
          </p>
        </div>
      )}

      <MapExcelRowDialog row={target} onOpenChange={(open) => !open && setTarget(null)} />
    </section>
  );
}
