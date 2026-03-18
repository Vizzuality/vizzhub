import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useProject } from '@/core/hooks/useProjects';
import { useProjectCostSummary, useProjectReportParts } from '../hooks/useProjectCosts';
import { formatPeriodDate, formatCurrency, burnColor, SELECT_CLASS } from '../utils/constants';
import type { ProjectCostSummary, ProjectReportPart } from '../types/tracker';

function SummaryCards({ summary }: { readonly summary: ProjectCostSummary }): JSX.Element {
  const burn = summary.burn_percentage ?? 0;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Budget</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {summary.budget === null ? '—' : formatCurrency(summary.budget)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Cost to Date</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">{formatCurrency(summary.total_cost)}</p>
          <p className="text-xs text-muted-foreground mt-1">
            Staff {formatCurrency(summary.staff_cost)} · Non-staff {formatCurrency(summary.non_staff_cost)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Burn %</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {summary.budget === null ? '—' : `${burn.toFixed(2)}%`}
          </p>
          {summary.budget !== null && (
            <div className="mt-2 h-2 w-full rounded-full bg-muted">
              <div
                className={`h-2 rounded-full ${burnColor(burn)}`}
                style={{ width: `${Math.min(burn, 100)}%` }}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
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

  return (
    <Card>
      <CardContent className="pt-6">
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
                {parts.map((part) => (
                  <tr key={part.id} className="border-b last:border-0">
                    <td className="py-2">{formatPeriodDate(part.period_date)}</td>
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

  if (summaryLoading || partsLoading) {
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
          {project?.name ?? 'Project'} — Tracker
        </h1>
      </div>

      <SummaryCards summary={summary} />

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
