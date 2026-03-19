import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useProject } from '@/core/hooks/useProjects';
import {
  useProjectCostSummary,
  useProjectReportParts,
  useProjectAggregations,
} from '../hooks/useProjectCosts';
import { formatPeriodDate, formatCurrency, SELECT_CLASS } from '../utils/constants';
import BurnDashboard, { useChartData, MonthlyCostsChart } from '../components/BurnDashboard';
import TimeByAreaTable from '../components/TimeByAreaTable';
import DaysByPeopleChart from '../components/DaysByPeopleChart';
import type { AggregationRow, ProjectCostSummary, ProjectReportPart } from '../types/tracker';

interface PeriodGroup {
  period: string;
  parts: ProjectReportPart[];
}

function groupByPeriod(parts: ProjectReportPart[]): PeriodGroup[] {
  const map = new Map<string, ProjectReportPart[]>();
  for (const part of parts) {
    const key = part.period_date;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(part);
  }
  return Array.from(map.entries()).map(([period, items]) => ({ period, parts: items }));
}

function PartsTable({
  parts,
  summary,
}: {
  readonly parts: ProjectReportPart[];
  readonly summary: ProjectCostSummary;
}): JSX.Element {
  const staffTotal = parts.reduce((sum, p) => sum + (p.cost ?? 0), 0);
  const nonStaffTotal = summary.non_staff_cost;
  const grandTotal = staffTotal + nonStaffTotal;
  const groups = useMemo(() => groupByPeriod(parts), [parts]);

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">
          Reports
        </div>
        {parts.length === 0 ? (
          <p className="text-muted-foreground text-sm">No report data</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Period</th>
                  <th className="pb-2 font-medium">Person</th>
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium text-right">%</th>
                  <th className="pb-2 font-medium text-right">Days</th>
                  <th className="pb-2 font-medium text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group, gi) => (
                  group.parts.map((part, pi) => (
                    <tr
                      key={part.id}
                      className={
                        pi < group.parts.length - 1
                          ? 'border-b'
                          : gi < groups.length - 1
                            ? 'border-b-2'
                            : ''
                      }
                    >
                      {pi === 0 && (
                        <td
                          className="py-2 font-medium align-top"
                          rowSpan={group.parts.length}
                        >
                          {formatPeriodDate(group.period)}
                        </td>
                      )}
                      <td className="py-2">{part.user_name ?? part.user_email ?? '—'}</td>
                      <td className="py-2">{part.functional_area ?? '—'}</td>
                      <td className="py-2 text-right">
                        {part.percentage === null
                          ? '—'
                          : `${(part.percentage * 100).toFixed(1)}%`}
                      </td>
                      <td className="py-2 text-right">
                        {part.days === null ? '—' : part.days.toFixed(2)}
                      </td>
                      <td className="py-2 text-right">
                        {part.cost === null ? '—' : formatCurrency(part.cost)}
                      </td>
                    </tr>
                  ))
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium">
                  <td className="pt-2" colSpan={5}>Staff</td>
                  <td className="pt-2 text-right">{formatCurrency(staffTotal)}</td>
                </tr>
                <tr className="font-medium">
                  <td className="pt-1" colSpan={5}>Non-staff</td>
                  <td className="pt-1 text-right">{formatCurrency(nonStaffTotal)}</td>
                </tr>
                <tr className="font-bold">
                  <td className="pt-1" colSpan={5}>Total</td>
                  <td className="pt-1 text-right">{formatCurrency(grandTotal)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DetailSection({
  summary,
  budget,
  projectEndDate,
  areaRows,
  userRows,
}: {
  readonly summary: ProjectCostSummary;
  readonly budget: number | null;
  readonly projectEndDate: string | null;
  readonly areaRows: AggregationRow[];
  readonly userRows: AggregationRow[];
}): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const { monthly, avgMonthlyBurn } = useChartData(summary.periods, budget, projectEndDate);

  const hasDetails = monthly.length > 0 || userRows.length > 0;

  return (
    <div className="space-y-4">
      {hasDetails && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors py-2"
        >
          {expanded
            ? <><ChevronUp className="w-4 h-4" />Show less</>
            : <><ChevronDown className="w-4 h-4" />Show more</>}
        </button>
      )}

      {expanded && (
        <>
          {monthly.length > 0 && (
            <MonthlyCostsChart data={monthly} avgMonthlyBurn={avgMonthlyBurn} />
          )}
          {userRows.length > 0 && (
            <DaysByPeopleChart rows={userRows} />
          )}
        </>
      )}

      <TimeByAreaTable rows={areaRows} />
    </div>
  );
}

export default function ProjectTrackerDetail(): JSX.Element {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { state, setState } = useUrlState({
    period: { defaultValue: '' },
  });

  const { data: project } = useProject(projectId || '');
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useProjectCostSummary(projectId || '');
  const { data: parts, isLoading: partsLoading } = useProjectReportParts(
    projectId || '',
    state.period || undefined,
  );
  const { data: areaAgg, isLoading: areaLoading } = useProjectAggregations(
    projectId || '',
    'functional_area',
  );
  const { data: userAgg, isLoading: userLoading } = useProjectAggregations(
    projectId || '',
    'user',
  );

  if (summaryLoading || partsLoading || areaLoading || userLoading) {
    return <LoadingSpinner />;
  }

  if (summaryError || !summary) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading cost data: {summaryError?.message || 'Not found'}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={() => navigate('/projects')}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <h1 className="text-2xl font-semibold">
          {project?.name ?? 'Project'}
        </h1>
      </div>

      <BurnDashboard
        periods={summary.periods}
        budget={summary.budget}
        projectEndDate={project?.end_date ?? null}
      />

      <DetailSection
        summary={summary}
        budget={summary.budget}
        projectEndDate={project?.end_date ?? null}
        areaRows={areaAgg?.rows ?? []}
        userRows={userAgg?.rows ?? []}
      />

      <div className="flex items-center gap-3">
        <label htmlFor="period-filter" className="text-sm font-medium">
          Period
        </label>
        <select
          id="period-filter"
          className={SELECT_CLASS}
          value={state.period}
          onChange={(e) => setState({ period: e.target.value })}
        >
          <option value="">All periods</option>
          {summary.periods.map((p) => (
            <option key={p.period_id} value={p.period_id}>
              {formatPeriodDate(p.date)}
            </option>
          ))}
        </select>
      </div>

      <PartsTable parts={parts ?? []} summary={summary} />
    </div>
  );
}
