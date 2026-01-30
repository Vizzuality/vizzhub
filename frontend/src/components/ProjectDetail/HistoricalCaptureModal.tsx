import { useState } from 'react';
import { Calendar, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useHistoricalCapture } from '@/hooks/useHistoricalCapture';
import type { CaptureReport } from '@/types';

interface HistoricalCaptureModalProps {
  projectId: string;
}

type CaptureMode = 'single' | 'range';

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

function getYearOptions(): number[] {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: 5 }, (_, i) => currentYear - 4 + i);
}

export default function HistoricalCaptureModal({
  projectId,
}: HistoricalCaptureModalProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<CaptureMode>('range');
  const [fromYear, setFromYear] = useState(new Date().getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(new Date().getFullYear());
  const [toMonth, setToMonth] = useState(new Date().getMonth() + 1);
  const [force, setForce] = useState(false);
  const [report, setReport] = useState<CaptureReport | null>(null);

  const { mutate, isPending, isError, error } = useHistoricalCapture(projectId);

  const handleCapture = (): void => {
    const request = {
      from_year: fromYear,
      from_month: fromMonth,
      to_year: mode === 'single' ? fromYear : toYear,
      to_month: mode === 'single' ? fromMonth : toMonth,
      force,
    };

    mutate(request, {
      onSuccess: (data) => {
        setReport(data);
      },
    });
  };

  const handleClose = (): void => {
    setOpen(false);
    setTimeout(() => {
      setReport(null);
    }, 300);
  };

  const handleOpenChange = (newOpen: boolean): void => {
    setOpen(newOpen);
    if (!newOpen) {
      setTimeout(() => {
        setReport(null);
      }, 300);
    }
  };

  const isValidRange = (): boolean => {
    if (mode === 'single') return true;
    const fromDate = new Date(fromYear, fromMonth - 1);
    const toDate = new Date(toYear, toMonth - 1);
    return fromDate <= toDate;
  };

  const renderModeSelector = (): JSX.Element => (
    <div className="flex flex-col gap-3">
      <Label className="text-sm font-medium">Capture Mode</Label>
      <div className="flex gap-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="captureMode"
            value="single"
            checked={mode === 'single'}
            onChange={() => setMode('single')}
            className="h-4 w-4 text-primary"
          />
          <span className="text-sm">Single Month</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="captureMode"
            value="range"
            checked={mode === 'range'}
            onChange={() => setMode('range')}
            className="h-4 w-4 text-primary"
          />
          <span className="text-sm">Month Range</span>
        </label>
      </div>
    </div>
  );

  const renderDateSelector = (
    label: string,
    yearValue: number,
    monthValue: number,
    onYearChange: (year: number) => void,
    onMonthChange: (month: number) => void
  ): JSX.Element => (
    <div className="flex flex-col gap-2">
      <Label className="text-sm font-medium">{label}</Label>
      <div className="flex gap-2">
        <select
          value={monthValue}
          onChange={(e) => onMonthChange(Number(e.target.value))}
          className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm flex-1"
        >
          {MONTHS.map((m, idx) => (
            <option key={idx + 1} value={idx + 1}>
              {m}
            </option>
          ))}
        </select>
        <select
          value={yearValue}
          onChange={(e) => onYearChange(Number(e.target.value))}
          className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm w-24"
        >
          {getYearOptions().map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
    </div>
  );

  const renderForm = (): JSX.Element => (
    <div className="flex flex-col gap-6 py-4">
      {renderModeSelector()}

      <div className="grid gap-4">
        {renderDateSelector(
          mode === 'single' ? 'Month' : 'From',
          fromYear,
          fromMonth,
          setFromYear,
          setFromMonth
        )}

        {mode === 'range' &&
          renderDateSelector('To', toYear, toMonth, setToYear, setToMonth)}
      </div>

      {!isValidRange() && (
        <p className="text-sm text-destructive flex items-center gap-1">
          <AlertCircle className="h-4 w-4" />
          End date must be after or equal to start date.
        </p>
      )}

      <div className="flex items-center justify-between rounded-lg border p-4">
        <div className="space-y-0.5">
          <Label htmlFor="force-switch" className="text-sm font-medium">
            Force Overwrite
          </Label>
          <p className="text-sm text-muted-foreground">
            Replace existing snapshots for the selected period.
          </p>
        </div>
        <Switch id="force-switch" checked={force} onCheckedChange={setForce} />
      </div>
    </div>
  );

  const renderResults = (): JSX.Element | null => {
    if (!report) return null;

    const { summary, details, errors } = report;

    return (
      <div className="flex flex-col gap-4 py-4">
        <div className="rounded-lg border p-4 bg-muted/50">
          <h4 className="font-medium mb-3">Summary</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Total Months:</span>
              <span className="font-medium">{summary.total_months}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-muted-foreground">Created:</span>
              <span className="font-medium">{summary.snapshots_created}</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-yellow-500" />
              <span className="text-muted-foreground">Skipped:</span>
              <span className="font-medium">{summary.snapshots_skipped}</span>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <span className="text-muted-foreground">Errors:</span>
              <span className="font-medium">{summary.errors}</span>
            </div>
          </div>
        </div>

        {details.length > 0 && (
          <div className="rounded-lg border p-4">
            <h4 className="font-medium mb-3">Details</h4>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {details.map((result, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-sm py-1 border-b last:border-0"
                >
                  <span>{result.month}</span>
                  <span
                    className={
                      result.status === 'created'
                        ? 'text-green-600'
                        : result.status === 'skipped'
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    }
                  >
                    {result.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {errors.length > 0 && (
          <div className="rounded-lg border border-destructive/50 p-4 bg-destructive/5">
            <h4 className="font-medium mb-3 text-destructive">Errors</h4>
            <div className="max-h-32 overflow-y-auto space-y-2">
              {errors.map((err, idx) => (
                <div key={idx} className="text-sm">
                  <span className="font-medium">{err.month}:</span>{' '}
                  <span className="text-muted-foreground">
                    {err.error_message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Calendar className="h-4 w-4" />
          Capture History
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Historical Capture
          </DialogTitle>
          <DialogDescription>
            {report
              ? 'Capture completed. Review the results below.'
              : 'Capture historical metrics and create snapshots for past months.'}
          </DialogDescription>
        </DialogHeader>

        {report ? renderResults() : renderForm()}

        {isError && !report && (
          <p className="text-sm text-destructive">
            Failed to capture history:{' '}
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        )}

        <DialogFooter>
          {report ? (
            <Button onClick={handleClose}>Close</Button>
          ) : (
            <>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                onClick={handleCapture}
                disabled={isPending || !isValidRange()}
              >
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Capturing...
                  </>
                ) : (
                  'Start Capture'
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
