import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, Send, RotateCcw, Info, CheckCircle2, CalendarClock, Eraser } from 'lucide-react';
import MoodDialog from './MoodDialog';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import { usePlannerSuggestions } from '@/core/hooks/usePlannerSuggestions';
import { useReport, useCreateReportPart, useUpdateReportPart, useUpdateReport } from '../hooks/useReports';
import ReportPartRow from './ReportPartRow';
import JiraIssuesPanel from './JiraIssuesPanel';
import { SELECT_CLASS } from '../utils/constants';
import type { Report } from '../types/tracker';

interface ReportEditorProps {
  readonly report: Report;
  readonly title: string;
  readonly emptyMessage?: string;
  readonly collapsible?: boolean;
  readonly periodDate?: string;
}

export default function ReportEditor({
  report,
  title,
  emptyMessage = 'No report parts yet. Add a project below.',
  collapsible = false,
  periodDate,
}: ReportEditorProps): JSX.Element {
  const [showMoodDialog, setShowMoodDialog] = useState(false);
  const { data: reportWithParts } = useReport(report.id);
  const createPart = useCreateReportPart(report.id);
  const updatePart = useUpdateReportPart(report.id);
  const updateReport = useUpdateReport(report.id, report.reporting_period_id);
  const { data: projects } = useActiveProjectSummaries();
  const { data: suggestions } = usePlannerSuggestions(periodDate ?? '');

  const parts = reportWithParts?.parts ?? [];
  const isEstimated = reportWithParts?.estimated ?? report.estimated;

  const totalPercentage = Math.round(
    parts.reduce((sum, p) => sum + (p.percentage ?? 0) * 100, 0) * 100,
  ) / 100;
  const isOverAllocated = totalPercentage > 100;
  const isExactly100 = totalPercentage === 100;

  const existingProjectIds = new Set(parts.map((p) => p.project_id));
  const availableProjects = projects?.filter((p) => !existingProjectIds.has(p.id)) ?? [];

  // Map project_id → suggested percentage for quick lookup
  const suggestionMap = useMemo(() => {
    const map = new Map<string, number>();
    if (suggestions?.suggestions) {
      for (const s of suggestions.suggestions) {
        map.set(s.project_id, s.percentage);
      }
    }
    return map;
  }, [suggestions]);

  // Auto-create report parts for planning projects not yet in the report.
  // Only for projects still active — avoids resurrecting finished projects
  // even if a stale planning row sneaks past the backend filter.
  const autoCreatedRef = useRef(new Set<string>());
  useEffect(() => {
    if (!suggestions?.suggestions || !reportWithParts || !projects) return;
    const activeIds = new Set(projects.map((p) => p.id));
    for (const s of suggestions.suggestions) {
      if (!activeIds.has(s.project_id)) continue;
      if (!existingProjectIds.has(s.project_id) && !autoCreatedRef.current.has(s.project_id)) {
        autoCreatedRef.current.add(s.project_id);
        createPart.mutate({
          report_id: report.id,
          project_id: s.project_id,
          percentage: 0,
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestions, reportWithParts, projects]);

  const handleAddProject = (projectId: string): void => {
    if (!projectId) return;
    createPart.mutate({
      report_id: report.id,
      project_id: projectId,
      percentage: 0,
    });
  };

  const handleClearAll = (): void => {
    for (const part of parts) {
      if (part.percentage != null && part.percentage > 0) {
        updatePart.mutate({ id: part.id, data: { percentage: 0 } });
      }
    }
  };

  const header = (
    <CardHeader className="py-3">
      <div className="flex items-center gap-3">
        {collapsible && (
          <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-data-[state=open]:rotate-90" />
        )}
        <CardTitle className="text-base">{title}</CardTitle>
        <span className="text-xs text-muted-foreground">
          {parts.length} {parts.length === 1 ? 'project' : 'projects'}
        </span>
        <span className={`text-xs ${isOverAllocated ? 'text-destructive font-bold' : 'text-muted-foreground'}`}>
          {totalPercentage.toFixed(1)}%
        </span>
        {isEstimated ? (
          <Badge variant="outline" className="bg-yellow-100 text-yellow-700">
            Estimated
          </Badge>
        ) : (
          <Badge variant="outline" className="bg-green-100 text-green-700">
            Confirmed
          </Badge>
        )}
      </div>
    </CardHeader>
  );

  const content = (
    <CardContent>
        {suggestions?.others_percentage != null && (
          <div
            className="flex items-center gap-2 mb-3 px-2 py-1.5 rounded-md bg-muted text-sm"
            style={{ color: 'var(--accent-green)' }}
          >
            <CalendarClock className="h-4 w-4 shrink-0" />
            <span>
              Others (from planning): <strong>{suggestions.others_percentage.toFixed(1)}%</strong>
            </span>
          </div>
        )}
        <div className="flex flex-col xl:flex-row gap-6">
          <div className="xl:w-3/5 xl:shrink-0">
            {parts.length > 0 && (
              <table className="w-full mb-3">
                <colgroup>
                  <col />
                  <col className="w-24" />
                  <col className="w-24" />
                  <col className="w-16" />
                  <col className="w-8" />
                </colgroup>
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="py-1 px-2">Project</th>
                    <th className="py-1 px-2 text-right whitespace-nowrap">From planning</th>
                    <th className="py-1 px-2">Percentage</th>
                    <th className="py-1 px-2 text-right">Days</th>
                    <th className="py-1 px-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {parts.map((part) => (
                    <ReportPartRow
                      key={part.id}
                      part={part}
                      reportId={report.id}
                      suggestedPercentage={suggestionMap.get(part.project_id)}
                    />
                  ))}
                  <tr className="border-t font-medium">
                    <td className="py-1 px-2 text-sm">Total</td>
                    <td></td>
                    <td className="py-1 px-2">
                      <span className={`text-sm ${isOverAllocated ? 'text-destructive font-bold' : ''}`}>
                        {totalPercentage.toFixed(1)}%
                      </span>
                      {isOverAllocated && (
                        <span className="text-xs text-destructive ml-2">
                          exceeds 100%
                        </span>
                      )}
                    </td>
                    <td className="py-1 px-2 text-right text-sm">
                      {parts.reduce((sum, p) => sum + (p.days ?? 0), 0).toFixed(2)}
                    </td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            )}
            {!parts.length && (
              <p className="text-sm text-muted-foreground mb-3">{emptyMessage}</p>
            )}
            <div className="flex items-center gap-2 mt-2">
              {availableProjects.length > 0 && (
                <select
                  value=""
                  onChange={(e) => handleAddProject(e.target.value)}
                  disabled={createPart.isPending}
                  className={`${SELECT_CLASS} h-8`}
                >
                  <option value="">Add project...</option>
                  {availableProjects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              )}
              {isEstimated && parts.length > 0 && totalPercentage > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1"
                  onClick={handleClearAll}
                  disabled={updatePart.isPending}
                >
                  <Eraser className="h-3.5 w-3.5" />
                  Clear all
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between mt-4 pt-3 border-t gap-4">
          {isEstimated ? (
            <>
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-foreground shrink-0" />
                <p className="text-sm text-foreground">
                  {!isExactly100 && parts.length > 0
                    ? <>Percentages must total <strong>100%</strong> to confirm (currently {totalPercentage.toFixed(1)}%).</>
                    : <>You can save partial data as you go. When your report is complete, click <strong>Confirm</strong> to mark it as final.</>
                  }
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => {
                  updateReport.mutate(
                    { estimated: false },
                    { onSuccess: () => setShowMoodDialog(true) },
                  );
                }}
                disabled={updateReport.isPending || parts.length === 0 || !isExactly100}
                className="shrink-0"
              >
                <Send className="w-3.5 h-3.5 mr-1.5" />
                Confirm
              </Button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                <p className="text-sm text-foreground">
                  This report has been confirmed. Reopen it if you need to make changes.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => updateReport.mutate({ estimated: true })}
                disabled={updateReport.isPending}
                className="shrink-0"
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                Reopen
              </Button>
            </>
          )}
            </div>
          </div>
          {periodDate && (
            <div className="flex-1 min-w-0">
              <JiraIssuesPanel periodDate={periodDate} />
            </div>
          )}
        </div>
      </CardContent>
    );

  const periodDateObj = periodDate ? new Date(periodDate) : null;

  const moodDialog = showMoodDialog && periodDateObj ? (
    <MoodDialog
      open={showMoodDialog}
      onClose={() => setShowMoodDialog(false)}
      reportId={report.id}
      periodId={report.reporting_period_id}
      periodMonth={periodDateObj.getMonth() + 1}
      periodYear={periodDateObj.getFullYear()}
    />
  ) : null;

  if (collapsible) {
    return (
      <>
        <Collapsible className="group">
          <Card>
            <CollapsibleTrigger asChild className="cursor-pointer w-full text-left">
              {header}
            </CollapsibleTrigger>
            <CollapsibleContent>
              {content}
            </CollapsibleContent>
          </Card>
        </Collapsible>
        {moodDialog}
      </>
    );
  }

  return (
    <>
      <Card>
        {header}
        {content}
      </Card>
      {moodDialog}
    </>
  );
}
