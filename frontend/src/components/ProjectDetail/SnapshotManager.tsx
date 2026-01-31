import { useState } from 'react';
import { useCapturePeriod, getCapturePeriodErrorMessage } from '../../hooks/usePeriodCapture';
import { useProjectSnapshots } from '../../hooks/useSnapshots';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Calendar, Download, Loader2, ChevronDown, ChevronRight, FileDown } from 'lucide-react';
import { MONTHS } from '@/constants/dates';
import { getYearOptions } from '@/utils/dateUtils';

interface SnapshotManagerProps {
  projectId: string;
}

export default function SnapshotManager({
  projectId,
}: SnapshotManagerProps): JSX.Element {
  const currentDate = new Date();
  const [isExpanded, setIsExpanded] = useState(false);
  const [year, setYear] = useState(currentDate.getFullYear());
  const [month, setMonth] = useState(currentDate.getMonth() + 1);
  const [forceCapture, setForceCapture] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const capturePeriod = useCapturePeriod(projectId, {
    onSuccess: () => setErrorMessage(null),
    onError: (error) => setErrorMessage(getCapturePeriodErrorMessage(error)),
  });
  const { data: snapshots } = useProjectSnapshots(projectId);

  const handleCapture = () => {
    setErrorMessage(null);
    capturePeriod.mutate({ year, month, force: forceCapture });
  };

  // Check if either snapshot type exists for the period
  const existingPeriods = new Set(
    snapshots?.map((s) => `${s.period_year}-${s.period_month}`) ?? []
  );
  const periodExists = existingPeriods.has(`${year}-${month}`);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <CardTitle className="flex items-center gap-2">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
            <Calendar className="h-5 w-5" />
            Historic Metrics
          </CardTitle>
          {!isExpanded && (
            <CardDescription>
              Click to capture metrics for a specific period
            </CardDescription>
          )}
          {isExpanded && (
            <CardDescription>
              Capture metrics from Jira and GitHub for a specific period.
              Creates both punctual (monthly) and cumulative (project-to-date) snapshots.
            </CardDescription>
          )}
        </CardHeader>
        {isExpanded && (
          <CardContent>
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex flex-col gap-2">
              <label htmlFor="year-select" className="text-sm font-medium">
                Year
              </label>
              <select
                id="year-select"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {getYearOptions().map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="month-select" className="text-sm font-medium">
                Month
              </label>
              <select
                id="month-select"
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {MONTHS.map((m, idx) => (
                  <option key={idx + 1} value={idx + 1}>{m}</option>
                ))}
              </select>
            </div>

            <Button
              onClick={handleCapture}
              disabled={capturePeriod.isPending || (periodExists && !forceCapture)}
            >
              {capturePeriod.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Capturing...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Capture Period
                </>
              )}
            </Button>
          </div>

          {periodExists && (
            <div className="mt-3 flex items-center gap-2">
              <input
                type="checkbox"
                id="force-capture"
                checked={forceCapture}
                onChange={(e) => setForceCapture(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <label htmlFor="force-capture" className="text-sm text-muted-foreground">
                Snapshots for {MONTHS[month - 1]} {year} already exist. Check to overwrite.
              </label>
            </div>
          )}

          {capturePeriod.isPending && (
            <p className="text-sm text-muted-foreground mt-3">
              Fetching metrics from Jira and GitHub. This may take up to 2 minutes...
            </p>
          )}

          {capturePeriod.isError && errorMessage && (
            <p className="text-sm text-destructive mt-2">
              {errorMessage}
            </p>
          )}

          {capturePeriod.isSuccess && (
            <p className="text-sm text-green-600 mt-2">
              Period captured successfully (both punctual and cumulative).
            </p>
          )}
          </CardContent>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileDown className="h-5 w-5" />
            Export
          </CardTitle>
          <CardDescription>
            Export project data and reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" disabled>
            <FileDown className="mr-2 h-4 w-4" />
            Export to CSV
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
