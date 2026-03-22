import { useMemo, useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronDown, Pencil, Calendar, ExternalLink } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';
import { projectsApi } from '@/core/services/projects';
import { formatDate } from '@/utils/formatters';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { Can, Action } from '@/core/permissions';
import { useProject } from '@/core/hooks/useProjects';
import {
  useProjectCostSummary,
  useProjectReportParts,
  useProjectAggregations,
} from '../hooks/useProjectCosts';
import { useBudgetLines } from '../hooks/useBudgetLines';
import { formatPeriodDate, formatCurrency, SELECT_CLASS } from '../utils/constants';
import BurnDashboard, { useChartData, MonthlyCostsChart } from '../components/BurnDashboard';
import TimeByAreaTable from '../components/TimeByAreaTable';
import DaysByPeopleChart from '../components/DaysByPeopleChart';
import ProgressCard from '../components/ProgressCard';
import InvoicesCard from '../components/InvoicesCard';
import NonStaffCostsCard from '../components/NonStaffCostsCard';
import type { AggregationRow, ProjectCostSummary, ProjectReportPart } from '../types/tracker';

function getRowBorderClass(
  partIdx: number,
  partsLen: number,
  groupIdx: number,
  groupsLen: number,
): string {
  if (partIdx < partsLen - 1) return 'border-b';
  if (groupIdx < groupsLen - 1) return 'border-b-2';
  return '';
}

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
                      className={getRowBorderClass(pi, group.parts.length, gi, groups.length)}
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

function InsightsSection({
  summary,
  projectEndDate,
  userRows,
}: {
  readonly summary: ProjectCostSummary;
  readonly projectEndDate: string | null;
  readonly userRows: AggregationRow[];
}): JSX.Element {
  const { monthly, avgMonthlyBurn } = useChartData(summary.periods, projectEndDate);

  const hasDetails = monthly.length > 0 || userRows.length > 0;

  if (!hasDetails) return <></>;

  return (
    <Collapsible defaultOpen>
      <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors py-2 group">
        Insights
        <ChevronDown className="w-4 h-4 transition-transform group-data-[state=closed]:-rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4">
        {userRows.length > 0 && (
          <DaysByPeopleChart rows={userRows} />
        )}
        {monthly.length > 0 && (
          <MonthlyCostsChart data={monthly} avgMonthlyBurn={avgMonthlyBurn} />
        )}
      </CollapsibleContent>
    </Collapsible>
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
  const { data: budgetLines } = useBudgetLines(projectId || '');

  const [links, setLinks] = useState<{ id: string; title: string | null; url: string | null; link_type: string | null }[]>([]);

  useEffect(() => {
    if (!projectId) return;
    projectsApi.getLinks(projectId).then(setLinks).catch(() => setLinks([]));
  }, [projectId]);

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

  const hasMoreInfo = project?.summary || project?.notes || links.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
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
          {(project?.start_date || project?.end_date) && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="w-4 h-4 shrink-0" />
              {project.start_date && formatDate(project.start_date)}
              {project.start_date && project.end_date && ' - '}
              {project.end_date && formatDate(project.end_date)}
            </div>
          )}
        </div>
        <Link to={`/projects/${projectId}/edit`}>
          <Button type="button" variant="ghost" size="sm" className="border border-input">
            <Pencil className="w-4 h-4 mr-2" />
            Edit
          </Button>
        </Link>
      </div>

      <BurnDashboard
        periods={summary.periods}
        budget={summary.budget}
        projectEndDate={project?.end_date ?? null}
      />

      {hasMoreInfo && (
        <Card>
          <CardContent className="pt-5">
            <Collapsible>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group">
                More Info
                <ChevronDown className="w-4 h-4 transition-transform group-data-[state=closed]:-rotate-90" />
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-4 space-y-4">
                {project?.summary && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Summary</p>
                    <p className="text-sm">{project.summary}</p>
                  </div>
                )}
                {project?.notes && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Notes</p>
                    <p className="text-sm whitespace-pre-line">{project.notes}</p>
                  </div>
                )}
                {links.length > 0 && (
                  <div>
                    <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-1">Links</p>
                    <div className="flex flex-wrap gap-3">
                      {links.map((link) => (
                        <a
                          key={link.id}
                          href={link.url ?? '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          {link.title || link.url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </CollapsibleContent>
            </Collapsible>
          </CardContent>
        </Card>
      )}

      <TimeByAreaTable rows={areaAgg?.rows ?? []} budgetLines={budgetLines} />

      <Can do={Action.TRACKER_MANAGE}>
        <InvoicesCard projectId={projectId || ''} />
      </Can>

      <NonStaffCostsCard
        projectId={projectId || ''}
        periods={summary.periods}
      />

      <Can do={Action.TRACKER_MANAGE}>
        <ProgressCard
          projectId={projectId || ''}
          periods={summary.periods}
        />
      </Can>

      <InsightsSection
        summary={summary}
        projectEndDate={project?.end_date ?? null}
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
