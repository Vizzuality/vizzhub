import { useCallback, useEffect, useMemo, useState } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { usePermission, Action } from '@/core/permissions';
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import { useReportableUsers } from '@/modules/capacity/hooks/useReportableUsers';
import { usePlannerData } from '@/modules/capacity/hooks/usePlannerData';
import { usePlannerMutations } from '@/modules/capacity/hooks/usePlannerMutations';
import { PlannerToolbar } from '@/modules/capacity/components/PlannerToolbar';
import { PlannerGrid } from '@/modules/capacity/components/PlannerGrid';
import {
  addMonths,
  defaultStart,
  endFromStart,
  snapToMondayString,
} from '@/modules/capacity/utils/plannerDates';
import type { PlannerGroup, PlannerRow } from '@/modules/capacity/types/planner';

const defaultStartDate = defaultStart();
const defaultEndDate = endFromStart(defaultStartDate);

export default function Planner(): JSX.Element {
  const canEditPlanner = usePermission(Action.CAPACITY_MANAGE);
  const { state, setState } = useUrlState({
    group: { defaultValue: 'project' },
    start: { defaultValue: defaultStartDate },
    end: { defaultValue: defaultEndDate },
    fa: { defaultValue: 'all' },
  });

  // Migrate stale URLs that could carry non-Monday dates from pre-UTC-fix
  // navigation. Keeps the wire date always Monday and never sends a Sunday
  // that makes the backend pad an uncovered week into the response.
  useEffect(() => {
    const snappedStart = snapToMondayString(state.start);
    const snappedEnd = snapToMondayString(state.end);
    if (snappedStart !== state.start || snappedEnd !== state.end) {
      setState({ start: snappedStart, end: snappedEnd });
    }
  }, [state.start, state.end, setState]);

  const { queueCellUpdate, flushUpdates, deleteRow, isSaving, pendingCount } =
    usePlannerMutations(state.start, state.end, state.group);
  const { data, isLoading, error } = usePlannerData(
    state.start, state.end, state.group, flushUpdates,
  );

  const { data: projects } = useActiveProjectSummaries();
  const { data: reportableUsers } = useReportableUsers();

  // Local-only rows not yet persisted (no cells saved yet)
  const [localRows, setLocalRows] = useState<PlannerRow[]>([]);

  const navigate = useCallback(
    async (direction: -1 | 1): Promise<void> => {
      await flushUpdates();
      setLocalRows([]);
      const newStart = addMonths(state.start, direction);
      setState({ start: newStart, end: addMonths(newStart, 6) });
    },
    [state.start, setState, flushUpdates],
  );

  const handlePrev = useCallback(() => navigate(-1), [navigate]);
  const handleNext = useCallback(() => navigate(1), [navigate]);

  const handleGroupByChange = useCallback(
    async (group: string): Promise<void> => {
      await flushUpdates();
      setLocalRows([]);
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

  const handleCommentChange = useCallback(
    (projectId: string, userId: string, week: string, comment: string | null): void => {
      const row = data?.groups
        .flatMap((g) => g.rows)
        .find((r) => r.project_id === projectId && r.user_id === userId);
      const percentage = row?.cells[week];
      if (percentage === undefined) return;
      queueCellUpdate({
        project_id: projectId,
        user_id: userId,
        week_start: week,
        percentage,
        comment,
      });
    },
    [data, queueCellUpdate],
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
          comments: {},
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
          comments: {},
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

  const pinnedProjectIds = useMemo(() => {
    if (!data) return new Set<string>();
    const ids: string[] = [];
    for (const g of data.groups) {
      for (const r of g.rows) {
        if (r.is_absence || r.is_other) ids.push(r.project_id);
      }
    }
    return new Set(ids);
  }, [data]);

  const addRowOptions = useMemo(() => {
    if (state.group === 'project' && reportableUsers) {
      return reportableUsers.map((u) => ({ id: u.id, name: u.name }));
    }
    if (state.group === 'user' && projects) {
      return projects
        .filter((p) => !pinnedProjectIds.has(p.id))
        .map((p) => ({ id: p.id, name: p.name }));
    }
    return [];
  }, [state.group, reportableUsers, projects, pinnedProjectIds]);

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
          warnings={data.warnings}
          groupBy={state.group}
          fa={state.fa}
          onCellChange={handleCellChange}
          onDeleteRow={deleteRow}
          onCommentChange={handleCommentChange}
          onAddRow={handleAddRow}
          addRowOptions={addRowOptions}
          canEdit={canEditPlanner}
        />
      )}
    </div>
  );
}
