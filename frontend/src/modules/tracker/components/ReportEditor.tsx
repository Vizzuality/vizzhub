import { ChevronRight } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import { useReport, useCreateReportPart } from '../hooks/useReports';
import ReportPartRow from './ReportPartRow';
import { SELECT_CLASS } from '../utils/constants';
import type { Report } from '../types/tracker';

interface ReportEditorProps {
  report: Report;
  title: string;
  emptyMessage?: string;
  collapsible?: boolean;
}

export default function ReportEditor({
  report,
  title,
  emptyMessage = 'No report parts yet. Add a project below.',
  collapsible = false,
}: ReportEditorProps): JSX.Element {
  const { data: reportWithParts } = useReport(report.id);
  const createPart = useCreateReportPart(report.id);
  const { data: projects } = useActiveProjectSummaries();

  const parts = reportWithParts?.parts ?? [];

  const totalPercentage = parts.reduce(
    (sum, p) => sum + (p.percentage ?? 0) * 100,
    0,
  );
  const isOverAllocated = totalPercentage > 100;

  const existingProjectIds = new Set(parts.map((p) => p.project_id));
  const availableProjects = projects?.filter((p) => !existingProjectIds.has(p.id)) ?? [];

  const handleAddProject = (projectId: string): void => {
    if (!projectId) return;
    createPart.mutate({
      report_id: report.id,
      project_id: projectId,
      percentage: 0,
    });
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
        {report.estimated && (
          <Badge variant="outline" className="bg-yellow-100 text-yellow-700">
            Estimated
          </Badge>
        )}
      </div>
    </CardHeader>
  );

  const content = (
    <CardContent>
        {parts.length > 0 && (
          <table className="w-full mb-3">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1 px-3">Project</th>
                <th className="py-1 px-3">Percentage</th>
                <th className="py-1 px-3 text-right">Days</th>
                <th className="py-1 px-3"></th>
              </tr>
            </thead>
            <tbody>
              {parts.map((part) => (
                <ReportPartRow
                  key={part.id}
                  part={part}
                  reportId={report.id}
                />
              ))}
              <tr className="border-t font-medium">
                <td className="py-2 px-3 text-sm">Total</td>
                <td className="py-2 px-3">
                  <span className={`text-sm ${isOverAllocated ? 'text-destructive font-bold' : ''}`}>
                    {totalPercentage.toFixed(1)}%
                  </span>
                  {isOverAllocated && (
                    <span className="text-xs text-destructive ml-2">
                      exceeds 100%
                    </span>
                  )}
                </td>
                <td className="py-2 px-3 text-right text-sm">
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
        {availableProjects.length > 0 && (
          <div className="flex items-center gap-2 mt-2">
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
          </div>
        )}
      </CardContent>
    );

  if (collapsible) {
    return (
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
    );
  }

  return (
    <Card>
      {header}
      {content}
    </Card>
  );
}
