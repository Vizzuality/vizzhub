import { AxiosError } from 'axios';
import { Button } from '@/shared/components/ui/button';
import { Loader2, Calendar } from 'lucide-react';
import type { Period } from '@/utils/dateUtils';
import { MONTHS } from '@/constants/dates';

interface EmptyPeriodOverlayProps {
  readonly period: Period;
  readonly onCapture: () => void;
  readonly isCapturing: boolean;
  readonly error?: Error | null;
}

export default function EmptyPeriodOverlay({
  period,
  onCapture,
  isCapturing,
  error,
}: EmptyPeriodOverlayProps): JSX.Element {
  const periodLabel = `${MONTHS[period.month - 1]} ${period.year}`;

  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-lg">
      <div className="text-center space-y-4 p-6">
        <Calendar className="w-12 h-12 mx-auto text-muted-foreground" />
        <div>
          <h3 className="text-lg font-semibold">No data for {periodLabel}</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Capture metrics from Jira and GitHub for this period
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive">
            {(error as AxiosError<{ detail?: string }>).response?.data?.detail
              || 'Failed to capture metrics. Please try again.'}
          </p>
        )}

        <Button onClick={onCapture} disabled={isCapturing}>
          {isCapturing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Capturing...
            </>
          ) : (
            'Capture metrics for this period'
          )}
        </Button>
      </div>
    </div>
  );
}
