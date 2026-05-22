import { useMemo, useState } from 'react';
import { useAccrualGrid } from '@/modules/accrual/hooks/useAccrualGrid';
import { useAccrualMutations } from '@/modules/accrual/hooks/useAccrualMutations';
import { AccrualGrid } from '@/modules/accrual/components/AccrualGrid';
import { AccrualToolbar } from '@/modules/accrual/components/AccrualToolbar';
import type { AccrualFilters } from '@/modules/accrual/components/AccrualToolbar';
import { usePermission, Action } from '@/core/permissions';

const CURRENT_YEAR = new Date().getFullYear();

export function Accrual(): JSX.Element {
  const [filters, setFilters] = useState<AccrualFilters>({
    year_from: CURRENT_YEAR,
    year_to: CURRENT_YEAR,
    status: 'live',
    currency: 'all',
  });

  const apiFilters = useMemo(
    () => ({
      year_from: filters.year_from,
      year_to: filters.year_to,
      ...(filters.status !== 'all' && { status: filters.status }),
      ...(filters.currency !== 'all' && { currency: filters.currency }),
    }),
    [filters],
  );

  const { data, isLoading, error } = useAccrualGrid(apiFilters);
  const { updateCell, bulkUpdate, failedCells, errorMessage } = useAccrualMutations();
  const canEdit = usePermission(Action.ACCRUAL_MANAGE);

  // Currencies actually present in the loaded grid (ISO-normalised) — fed to the toolbar
  const currencies = useMemo(() => {
    const codes = new Set<string>();
    for (const project of data?.projects ?? []) {
      const raw = (project.currency ?? '').toLowerCase();
      const code =
        raw === 'dollar' ? 'USD' : raw === 'euro' ? 'EUR' : (project.currency ?? '').toUpperCase();
      if (code && code !== 'EUR') codes.add(code);
    }
    return Array.from(codes).sort();
  }, [data?.projects]);

  const handleCellChange = async (
    projectId: string,
    year: number,
    month: number,
    amount: string,
  ): Promise<void> => {
    const existing = data?.cells.find(
      (c) => c.project_id === projectId && c.year === year && c.month === month,
    );
    if (existing) {
      await updateCell(existing.id, amount);
    } else {
      await bulkUpdate([{ project_id: projectId, year, month, amount }]);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual grid</h1>
      </div>
      <AccrualToolbar filters={filters} onChange={setFilters} currencies={currencies} />
      {errorMessage && (
        <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}
      {error ? (
        <p className="text-sm text-destructive">Failed to load grid.</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <AccrualGrid
          projects={data?.projects ?? []}
          cells={data?.cells ?? []}
          months={data?.months ?? []}
          onCellChange={handleCellChange}
          canEdit={canEdit}
          failedCells={failedCells}
        />
      )}
    </div>
  );
}
