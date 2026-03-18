import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useReportingPeriod } from '../hooks/useReportingPeriods';
import { useReports } from '../hooks/useReports';
import ReportEditor from '../components/ReportEditor';
import PeriodStatusBadge from '../components/PeriodStatusBadge';
import type { Report } from '../types/tracker';
import { formatPeriodDate } from '../utils/constants';

function reportTitle(report: Report): string {
  return report.user_name || report.user_email || report.user_id.slice(0, 8);
}

export default function PeriodDetail(): JSX.Element {
  const { periodId } = useParams<{ periodId: string }>();
  const navigate = useNavigate();
  const { data: period, isLoading: periodLoading, error: periodError } =
    useReportingPeriod(periodId || '');
  const { data: reports, isLoading: reportsLoading } = useReports(periodId || '');

  if (periodLoading || reportsLoading) {
    return <LoadingSpinner />;
  }

  if (periodError || !period) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading period: {periodError?.message || 'Not found'}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/admin/tracker/periods')}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <h1 className="text-2xl font-semibold">
          {formatPeriodDate(period.date)}
        </h1>
        <PeriodStatusBadge status={period.status} />
      </div>

      {!reports?.length ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-sm">
              No reports for this period yet. Use "Add My Report" from the user menu.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <ReportEditor
              key={report.id}
              report={report}
              title={reportTitle(report)}
              emptyMessage="No report parts yet."
              collapsible
            />
          ))}
        </div>
      )}
    </div>
  );
}
