import { useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  useReportingPeriods,
  useActivatePeriod,
  useFinishPeriod,
  useReactivatePeriod,
  useDeletePeriod,
} from '../hooks/useReportingPeriods';
import PeriodForm from '../components/PeriodForm';
import PeriodStatusBadge from '../components/PeriodStatusBadge';
import type { ReportingPeriod } from '../types/tracker';
import { formatPeriodDate } from '../utils/constants';

function PeriodActions({ period }: Readonly<{ period: ReportingPeriod }>): JSX.Element {
  const activate = useActivatePeriod();
  const finish = useFinishPeriod();
  const reactivate = useReactivatePeriod();
  const deletePeriod = useDeletePeriod();

  return (
    <div className="flex gap-1">
      {period.status === 'unstarted' && (
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => { e.stopPropagation(); activate.mutate(period.id); }}
          disabled={activate.isPending}
        >
          Activate
        </Button>
      )}
      {period.status === 'active' && (
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => { e.stopPropagation(); finish.mutate(period.id); }}
          disabled={finish.isPending}
        >
          Finish
        </Button>
      )}
      {period.status === 'finished' && (
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => { e.stopPropagation(); reactivate.mutate(period.id); }}
          disabled={reactivate.isPending}
        >
          Reactivate
        </Button>
      )}
      {period.report_count === 0 && (
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={(e) => { e.stopPropagation(); deletePeriod.mutate(period.id); }}
          disabled={deletePeriod.isPending}
        >
          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
        </Button>
      )}
    </div>
  );
}

export default function ReportingPeriods(): JSX.Element {
  const navigate = useNavigate();
  const { data: periods, isLoading, error } = useReportingPeriods();

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">
            Error loading periods: {error.message}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Reporting Periods</h1>
        <PeriodForm />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Periods</CardTitle>
        </CardHeader>
        <CardContent>
          {!periods?.length ? (
            <p className="text-muted-foreground text-sm">
              No reporting periods yet. Create one to get started.
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="py-2 px-3">Period</th>
                  <th className="py-2 px-3">Base Rate</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => (
                  <tr
                    key={period.id}
                    className="border-b hover:bg-muted/50 cursor-pointer"
                    onClick={() => navigate(`/admin/tracker/periods/${period.id}`)}
                  >
                    <td className="py-2 px-3 font-medium">
                      {formatPeriodDate(period.date)}
                    </td>
                    <td className="py-2 px-3">{period.base_rate.toFixed(2)}</td>
                    <td className="py-2 px-3">
                      <PeriodStatusBadge status={period.status} />
                    </td>
                    <td className="py-2 px-3">
                      <PeriodActions period={period} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
