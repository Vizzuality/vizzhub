import { useCallback, useEffect, useMemo, useState } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import { useReportableUsers } from '@/modules/capacity/hooks/useReportableUsers';
import { usePlannerData } from '@/modules/capacity/hooks/usePlannerData';
import { usePlannerMutations } from '@/modules/capacity/hooks/usePlannerMutations';
import { PlannerToolbar } from '@/modules/capacity/components/PlannerToolbar';
import { PlannerGrid } from '@/modules/capacity/components/PlannerGrid';
import type { PlannerGroup, PlannerRow } from '@/modules/capacity/types/planner';

function defaultStart(): string {
  const d = new Date();
  // Snap to Monday of current week
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  return monday.toISOString().slice(0, 10);
}

function addMonths(dateStr: string, months: number): string {
  const d = new Date(dateStr + 'T00:00:00');
  d.setMonth(d.getMonth() + months);
  // Snap to Monday
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return d.toISOString().slice(0, 10);
}

function endFromStart(start: string): string {
  return addMonths(start, 6);
}

const defaultStartDate = defaultStart();
const defaultEndDate = endFromStart(defaultStartDate);

export default function Planner(): JSX.Element {
  const { state, setState } = useUrlState({
    group: { defaultValue: 'project' },
    start: { defaultValue: defaultStartDate },
    end: { defaultValue: defaultEndDate },
    fa: { defaultValue: 'all' },
  });

  const { queueCellUpdate, flushUpdates, deleteRow, isSaving, pendingCount } =
    usePlannerMutations(state.start, state.end, state.group);
  const { data, isLoading, error } = usePlannerData(
    state.start, state.end, state.group, flushUpdates,
  );

  const { data: projects } = useActiveProjectSummaries();
  const { data: reportableUsers } = useReportableUsers();

  // Local-only rows not yet persisted (no cells saved yet)
  const [localRows, setLocalRows] = useState<PlannerRow[]>([]);

  const handlePrev = useCallback((): void => {
    flushUpdates();
    const newStart = addMonths(state.start, -1);
    setState({ start: newStart, end: addMonths(newStart, 6) });
  }, [state.start, setState, flushUpdates]);

  const handleNext = useCallback((): void => {
    flushUpdates();
    const newStart = addMonths(state.start, 1);
    setState({ start: newStart, end: addMonths(newStart, 6) });
  }, [state.start, setState, flushUpdates]);

  const handleGroupByChange = useCallback(
    (group: string): void => {
      flushUpdates();
      setState({ group });
    },
    [setState, flushUpdates],
  );

  const handleCellChange = useCallback(
    (projectId: string, userId: string, week: string, value: number | null): void => {
      queueCellUpdate({
        project_id: projectId,
        user_id: userId,
        week_start: week,
        percentage: value,
      });
    },
    [queueCellUpdate],
  );

  // Merge server data with local phantom rows
  const mergedGroups = useMemo((): PlannerGroup[] => {
    if (!data) return [];
    const groups = data.groups.map((g) => ({ ...g, rows: [...g.rows] }));
    for (const lr of localRows) {
      const groupId = state.group === 'project' ? lr.project_id : lr.user_id;
      const existing = groups.find((g) => g.id === groupId);
      if (existing) {
        existing.rows.push(lr);
      } else {
        groups.push({
          id: groupId,
          name: state.group === 'project' ? lr.project_name : lr.user_name,
          rows: [lr],
        });
      }
    }
    return groups;
  }, [data, localRows, state.group]);

  const handleAddRow = useCallback(
    (groupId: string, targetId: string): void => {
      // Build a phantom row from the selected user/project
      let newRow: PlannerRow;
      if (state.group === 'project') {
        const user = reportableUsers?.find((u) => u.id === targetId);
        if (!user) return;
        newRow = {
          user_id: user.id,
          user_name: user.name,
          functional_area: '',
          project_id: groupId,
          project_name: data?.groups.find((g) => g.id === groupId)?.name ?? '',
          cells: {},
        };
      } else {
        const project = projects?.find((p) => p.id === targetId);
        if (!project) return;
        newRow = {
          user_id: groupId,
          user_name: data?.groups.find((g) => g.id === groupId)?.name ?? '',
          functional_area: '',
          project_id: project.id,
          project_name: project.name,
          cells: {},
        };
      }
      setLocalRows((prev) => [...prev, newRow]);
    },
    [state.group, reportableUsers, projects, data],
  );

  // Clear local rows that now exist in server data
  useEffect(() => {
    if (!data) return;
    const serverKeys = new Set(
      data.groups.flatMap((g) =>
        g.rows.map((r) => `${r.project_id}:${r.user_id}`),
      ),
    );
    setLocalRows((prev) =>
      prev.filter((lr) => !serverKeys.has(`${lr.project_id}:${lr.user_id}`)),
    );
  }, [data]);

  const addRowOptions = useMemo(() => {
    if (state.group === 'project' && reportableUsers) {
      return reportableUsers.map((u) => ({ id: u.id, name: u.name }));
    }
    if (state.group === 'user' && projects) {
      return projects.map((p) => ({ id: p.id, name: p.name }));
    }
    return [];
  }, [state.group, reportableUsers, projects]);

  return (
    <div className="space-y-4 p-6">
      <PlannerToolbar
        groupBy={state.group}
        onGroupByChange={handleGroupByChange}
        fa={state.fa}
        onFaChange={(fa) => setState({ fa })}
        onPrev={handlePrev}
        onNext={handleNext}
        isSaving={isSaving}
        pendingCount={pendingCount}
      />

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load planner data
        </div>
      )}

      {data && (
        <PlannerGrid
          groups={mergedGroups}
          weeks={data.weeks}
          groupBy={state.group}
          fa={state.fa}
          onCellChange={handleCellChange}
          onDeleteRow={deleteRow}
          onAddRow={handleAddRow}
          addRowOptions={addRowOptions}
        />
      )}
    </div>
  );
}
