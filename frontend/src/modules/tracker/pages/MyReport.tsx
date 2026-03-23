import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, HelpCircle, History } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useAuth } from '@/core/hooks/useAuth';
import {
  useReportingPeriods,
} from '../hooks/useReportingPeriods';
import {
  useReports,
  useCreateReport,
} from '../hooks/useReports';
import ReportEditor from '../components/ReportEditor';
import PeriodStatusBadge from '../components/PeriodStatusBadge';
import { formatPeriodDate } from '../utils/constants';

export default function MyReport(): JSX.Element {
  const { periodId } = useParams<{ periodId: string }>();
  const navigate = useNavigate();
  const auth = useAuth();
  const { data: periods, isLoading: periodsLoading } = useReportingPeriods();

  const targetPeriod = periodId
    ? periods?.find((p) => p.id === periodId)
    : periods?.find((p) => p.status === 'active');

  const { data: reports, isLoading: reportsLoading } = useReports(targetPeriod?.id ?? '');
  const createReport = useCreateReport(targetPeriod?.id ?? '');

  const myReport = reports?.find(
    (r) => r.user_email === auth.user?.email,
  );

  const isActivePeriod = targetPeriod?.status === 'active';

  const autoCreateAttempted = useRef(false);

  useEffect(() => {
    if (isActivePeriod && targetPeriod && reports && !myReport && !autoCreateAttempted.current) {
      autoCreateAttempted.current = true;
      createReport.mutate({ reporting_period_id: targetPeriod.id });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActivePeriod, targetPeriod, reports, myReport]);

  if (periodsLoading || reportsLoading) {
    return <LoadingSpinner />;
  }

  if (!targetPeriod) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-muted-foreground">
            {periodId ? 'Period not found.' : 'No active reporting period. Ask an admin to activate a period.'}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {periodId && (
            <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tracker/my-reports')}>
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
          )}
          <h1 className="text-2xl font-semibold">
            {formatPeriodDate(targetPeriod.date)}
          </h1>
          <PeriodStatusBadge status={targetPeriod.status} />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => navigate('/tracker/how-to-report')}
          >
            <HelpCircle className="h-4 w-4" />
            How to report
          </Button>
          {!periodId && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={() => navigate('/tracker/my-reports')}
            >
              <History className="h-4 w-4" />
              Report history
            </Button>
          )}
        </div>
      </div>

      {myReport ? (
        <ReportEditor report={myReport} title="My Time Report" periodDate={targetPeriod.date} />
      ) : (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              {isActivePeriod ? 'Creating your report...' : 'No report for this period.'}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
