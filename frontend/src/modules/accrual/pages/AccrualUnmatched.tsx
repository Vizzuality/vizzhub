import { Loader2 } from 'lucide-react';
import { useDriftSummary } from '@/modules/accrual/hooks/useUnmatched';
import { UnmatchedExcelRowsSection } from '@/modules/accrual/components/UnmatchedExcelRowsSection';
import { DriftFindingsSection } from '@/modules/accrual/components/DriftFindingsSection';

export function AccrualUnmatched(): JSX.Element {
  const { data: summary, isLoading } = useDriftSummary();

  return (
    <div className="p-6 space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Accrual — unmatched & drift</h1>
        <p className="text-sm text-muted-foreground">
          Reconcile divergences between the CEO's Excel forecast and tracker state. Resolutions
          persist across importer runs, so the next import will respect manual mappings and
          acknowledged drift.
        </p>
      </header>

      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : summary ? (
        (() => {
          // ``missing_tracker`` is surfaced as its own section (Excel rows
          // without a tracker match) — excluded from the banner to avoid
          // double-counting against the drift findings below.
          const visibleKinds = Object.entries(summary.by_kind).filter(
            ([k]) => k !== 'missing_tracker',
          );
          const driftOpen = visibleKinds.reduce((sum, [, b]) => sum + b.open, 0);
          if (driftOpen === 0) return null;
          return (
            <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
              <div className="flex flex-wrap gap-x-6 gap-y-1">
                <span>
                  <strong>{driftOpen}</strong> open drift finding
                  {driftOpen === 1 ? '' : 's'}
                </span>
                {visibleKinds.map(([kind, bucket]) => (
                  <span key={kind} className="text-xs text-amber-800/80 dark:text-amber-200/80">
                    {kind}: {bucket.open} open / {bucket.resolved} resolved
                  </span>
                ))}
              </div>
            </div>
          );
        })()
      ) : null}

      <UnmatchedExcelRowsSection />

      <DriftFindingsSection
        kinds={['date_extend', 'date_shrink', 'value_drift', 'status_stale']}
        title="Drift findings"
        description="Date / value / status divergences between Excel and tracker. Resolve with a short note explaining what action you took outside this view."
      />
    </div>
  );
}
