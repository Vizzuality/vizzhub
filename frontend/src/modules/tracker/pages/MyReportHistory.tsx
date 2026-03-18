import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useAuth } from '@/core/hooks/useAuth';
import { useReportingPeriods } from '../hooks/useReportingPeriods';
import { useReports } from '../hooks/useReports';
import PeriodStatusBadge from '../components/PeriodStatusBadge';
import type { ReportingPeriod } from '../types/tracker';
import { formatPeriodDate } from '../utils/constants';

function PeriodReportRow({
  period,
  userEmail,
}: {
  period: ReportingPeriod;
  userEmail: string;
}): JSX.Element | null {
  const { data: reports } = useReports(period.id);
  const myReport = reports?.find((r) => r.user_email === userEmail);

  if (!reports) return null;

  return (
    <tr className="border-b hover:bg-muted/50">
      <td className="py-2 px-3 font-medium">
        {myReport ? (
          <Link
            to={`/tracker/my-report/${period.id}`}
            className="text-primary hover:underline"
          >
            {formatPeriodDate(period.date)}
          </Link>
        ) : (
          formatPeriodDate(period.date)
        )}
      </td>
      <td className="py-2 px-3">
        <PeriodStatusBadge status={period.status} />
      </td>
      <td className="py-2 px-3 text-sm">
        {myReport ? (
          <Link
            to={`/tracker/my-report/${period.id}`}
            className="text-primary hover:underline"
          >
            View / Edit
          </Link>
        ) : (
          <span className="text-muted-foreground">No report</span>
        )}
      </td>
    </tr>
  );
}

export default function MyReportHistory(): JSX.Element {
  const navigate = useNavigate();
  const auth = useAuth();
  const { data: periods, isLoading } = useReportingPeriods();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tracker/my-report')}>
          <ArrowLeft className="h-4 w-4" />
          Back to current
        </Button>
        <h1 className="text-2xl font-semibold">My Report History</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Reports by Period</CardTitle>
        </CardHeader>
        <CardContent>
          {!periods?.length ? (
            <p className="text-muted-foreground text-sm">No periods yet.</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="py-2 px-3">Period</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3">My Report</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <PeriodReportRow
                    key={period.id}
                    period={period}
                    userEmail={auth.user?.email ?? ''}
                  />
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
