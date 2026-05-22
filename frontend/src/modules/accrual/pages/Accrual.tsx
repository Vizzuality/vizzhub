import { useEffect, useMemo, useRef, useState } from 'react';
import { useAccrualGrid } from '@/modules/accrual/hooks/useAccrualGrid';
import { useAccrualMutations } from '@/modules/accrual/hooks/useAccrualMutations';
import { AccrualGrid } from '@/modules/accrual/components/AccrualGrid';
import { AccrualToolbar } from '@/modules/accrual/components/AccrualToolbar';
import type { AccrualFilters } from '@/modules/accrual/components/AccrualToolbar';
import { usePermission, Action } from '@/core/permissions';

const CURRENT_YEAR = new Date().getFullYear();

function clampYear(year: number, min: number, max: number): number {
  return Math.max(min, Math.min(year, max));
}

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

  // One-shot snap on first response: if the saved filter is outside the
  // data's range, fold it back in so the user lands on actual data.
  const snappedRef = useRef(false);
  useEffect(() => {
    if (snappedRef.current || !data?.bounds) return;
    snappedRef.current = true;
    const { min_year, max_year } = data.bounds;
    setFilters((prev) => {
      const yf = clampYear(prev.year_from, min_year, max_year);
      const yt = clampYear(prev.year_to, min_year, max_year);
      if (yf === prev.year_from && yt === prev.year_to) return prev;
      return { ...prev, year_from: yf, year_to: Math.max(yt, yf) };
    });
  }, [data?.bounds]);

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
      <AccrualToolbar
        filters={filters}
        onChange={setFilters}
        currencies={data?.available_currencies ?? []}
        minYear={data?.bounds?.min_year}
        maxYear={data?.bounds?.max_year}
      />
      {errorMessage && (
        <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}
      {error ? (
        <p className="text-sm text-destructive">Failed to load grid.</p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data && data.projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No projects match the current filters.
        </p>
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
