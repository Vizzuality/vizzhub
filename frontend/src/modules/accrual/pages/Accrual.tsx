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
    issues_only: false,
  });

  const apiFilters = useMemo(
    () => ({ year_from: filters.year_from, year_to: filters.year_to }),
    [filters.year_from, filters.year_to],
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

  // Projects with at least one non-zero cell in the visible range. The grid
  // endpoint already clips cells by [year_from, year_to], so a simple set
  // suffices — no extra date check.
  const projectsWithCells = useMemo(() => {
    if (!data) return new Set<string>();
    const ids = new Set<string>();
    for (const c of data.cells) {
      if (Number(c.amount) !== 0) ids.add(c.project_id);
    }
    return ids;
  }, [data]);

  const visibleProjects = useMemo(() => {
    if (!data) return [];
    const withCells = data.projects.filter((p) => projectsWithCells.has(p.id));
    if (!filters.issues_only) return withCells;
    return withCells.filter(
      (p) => p.health.status === 'critical' || p.health.status === 'warning',
    );
  }, [data, projectsWithCells, filters.issues_only]);

  const issuesCount = useMemo(
    () =>
      visibleProjects.filter((p) => p.health.status === 'critical' || p.health.status === 'warning')
        .length,
    [visibleProjects],
  );

  function renderGrid(): JSX.Element {
    if (error) return <p className="text-sm text-destructive">Failed to load grid.</p>;
    if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
    if (visibleProjects.length === 0) {
      return <p className="text-sm text-muted-foreground">No projects with accrual data in this range.</p>;
    }
    return (
      <AccrualGrid
        projects={visibleProjects}
        cells={data?.cells ?? []}
        months={data?.months ?? []}
        onCellChange={handleCellChange}
        canEdit={canEdit}
        failedCells={failedCells}
      />
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Accrual grid</h1>
      </div>
      <AccrualToolbar
        filters={filters}
        onChange={setFilters}
        minYear={data?.bounds?.min_year}
        maxYear={data?.bounds?.max_year}
      />
      {issuesCount > 0 && !filters.issues_only && (
        <button
          type="button"
          onClick={() => setFilters((f) => ({ ...f, issues_only: true }))}
          className="w-full rounded border border-amber-300 bg-amber-50 px-3 py-2 text-left text-sm text-amber-900 hover:bg-amber-100"
        >
          <strong>{issuesCount}</strong> project{issuesCount === 1 ? '' : 's'} need{issuesCount === 1 ? 's' : ''} review — click to filter
        </button>
      )}
      {errorMessage && (
        <div className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}
      {renderGrid()}
    </div>
  );
}
