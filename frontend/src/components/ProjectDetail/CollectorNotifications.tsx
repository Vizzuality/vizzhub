import { AxiosError } from 'axios';
import { X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

function getErrorDetail(error: Error): string {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return axiosError.response?.data?.detail || 'An unknown error occurred';
}

interface CollectorNotificationsProps {
  error: Error | null;
  isSuccess: boolean;
  dismissedSuccess: boolean;
  onDismissSuccess: () => void;
}

export default function CollectorNotifications({
  error,
  isSuccess,
  dismissedSuccess,
  onDismissSuccess,
}: CollectorNotificationsProps): JSX.Element | null {
  const hasNotification = error || (isSuccess && !dismissedSuccess);

  if (!hasNotification) return null;

  const errorDetail = error ? getErrorDetail(error) : '';

  return (
    <>
      {error && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-red/10 border-score-red/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-red">Failed to collect metrics</p>
              <p className="text-sm mt-1 text-score-red/80">
                {errorDetail}
              </p>
              {errorDetail.includes('authentication') && (
                <div className="mt-3 p-3 bg-score-red/10 rounded border border-score-red/30">
                  <p className="text-sm font-medium text-score-red mb-2">
                    OAuth not configured
                  </p>
                  <p className="text-xs text-score-red/80 mb-2">
                    You need to authorize Jira OAuth to collect metrics. This only needs to be
                    done once.
                  </p>
                  <a
                    href="http://localhost:8000/api/oauth/jira/authorize"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block text-xs font-medium text-primary hover:underline"
                  >
                    → Authorize Jira OAuth
                  </a>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {isSuccess && !dismissedSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-green/10 border-score-green/30">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-score-green">
                Metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={onDismissSuccess}
                className="text-score-green hover:text-score-green/70"
              >
                <X className="w-5 h-5" />
              </button>
            </CardContent>
          </Card>
        </>
      )}
    </>
  );
}
