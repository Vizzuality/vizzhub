import { useState, useEffect } from 'react';
import { useCaptureHistoryJob, useJobStatus } from '@/core/hooks/useJobs';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { MonthYearPicker } from '@/shared/components/ui/month-year-picker';
import { History, Loader2, ChevronDown, ChevronRight } from 'lucide-react';

const STORAGE_KEY_PREFIX = 'capture_job_';

function saveActiveJob(projectId: string, jobId: string): void {
  localStorage.setItem(`${STORAGE_KEY_PREFIX}${projectId}`, jobId);
}

function loadActiveJob(projectId: string): string | null {
  return localStorage.getItem(`${STORAGE_KEY_PREFIX}${projectId}`);
}

function clearActiveJob(projectId: string): void {
  localStorage.removeItem(`${STORAGE_KEY_PREFIX}${projectId}`);
}

interface HistoricalCaptureSectionProps {
  readonly projectId: string;
}

export default function HistoricalCaptureSection({
  projectId,
}: HistoricalCaptureSectionProps): JSX.Element {
  const currentDate = new Date();
  const [isExpanded, setIsExpanded] = useState(false);

  // Date range state
  const [fromYear, setFromYear] = useState(currentDate.getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(currentDate.getFullYear());
  const [toMonth, setToMonth] = useState(currentDate.getMonth() + 1);

  // Active job state - initialize from localStorage
  const [activeJobId, setActiveJobId] = useState<string | null>(() =>
    loadActiveJob(projectId),
  );

  // Hooks
  const captureHistoryJob = useCaptureHistoryJob(projectId);
  const { data: job } = useJobStatus(activeJobId);

  const isJobActive = job?.status === 'pending' || job?.status === 'running';

  // Clear localStorage when job completes, fails, or is cancelled
  useEffect(() => {
    if (
      job?.status === 'completed' ||
      job?.status === 'failed' ||
      job?.status === 'cancelled'
    ) {
      clearActiveJob(projectId);
    }
  }, [job?.status, projectId]);

  const handleStartCapture = async (): Promise<void> => {
    const result = await captureHistoryJob.mutateAsync({
      from_year: fromYear,
      from_month: fromMonth,
      to_year: toYear,
      to_month: toMonth,
      force: true,
    });
    setActiveJobId(result.id);
    saveActiveJob(projectId, result.id);
  };

  // Calculate month count for display
  const monthCount = (toYear - fromYear) * 12 + (toMonth - fromMonth) + 1;

  return (
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
          <History className="h-5 w-5" />
          Batch Historical Capture
        </CardTitle>
        {isExpanded && (
          <CardDescription>
            Capture metrics for multiple months at once. This runs in the background.
          </CardDescription>
        )}
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-4">
          {/* Date range selectors */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">From</span>
            <MonthYearPicker
              month={fromMonth}
              year={fromYear}
              onMonthChange={setFromMonth}
              onYearChange={setFromYear}
              disabled={isJobActive}
            />
            <span className="text-sm text-muted-foreground">to</span>
            <MonthYearPicker
              month={toMonth}
              year={toYear}
              onMonthChange={setToMonth}
              onYearChange={setToYear}
              disabled={isJobActive}
            />
          </div>

          {/* Month count info */}
          {monthCount > 0 && !isJobActive && (
            <p className="text-sm text-muted-foreground">
              Will capture {monthCount} month{monthCount > 1 ? 's' : ''}.
              Estimated time: ~{Math.ceil(monthCount * 2.5)} minutes.
            </p>
          )}

          {/* Start button */}
          {!isJobActive && (
            <Button
              onClick={handleStartCapture}
              disabled={captureHistoryJob.isPending || monthCount <= 0}
            >
              {captureHistoryJob.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <History className="mr-2 h-4 w-4" />
                  Start Batch Capture
                </>
              )}
            </Button>
          )}

          {/* Progress display */}
          {job && isJobActive && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{job.progress_message || 'Initializing...'}</span>
                <span>{job.progress}%</span>
              </div>
              <Progress value={job.progress} />
              <p className="text-xs text-muted-foreground">
                This process runs in the background. You can close this page.
              </p>
            </div>
          )}

          {/* Completed state */}
          {job?.status === 'completed' && (
            <div className="text-sm text-green-600 bg-green-50 p-3 rounded">
              Capture completed.{' '}
              {job.result?.summary?.snapshots_created ?? 0} snapshots created.
              {(job.result?.summary?.errors ?? 0) > 0 && (
                <span className="text-amber-600">
                  {' '}
                  ({job.result?.summary?.errors} errors)
                </span>
              )}
            </div>
          )}

          {/* Failed state */}
          {job?.status === 'failed' && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
              Capture failed: {job.error_message}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
