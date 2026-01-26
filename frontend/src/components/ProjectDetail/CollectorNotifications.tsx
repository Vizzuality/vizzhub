import { X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

interface CollectorNotificationsProps {
  jiraError: Error | null;
  jiraSuccess: boolean;
  dismissedJiraSuccess: boolean;
  onDismissJiraSuccess: () => void;
  githubError: Error | null;
  githubSuccess: boolean;
  dismissedGitHubSuccess: boolean;
  onDismissGitHubSuccess: () => void;
}

export default function CollectorNotifications({
  jiraError,
  jiraSuccess,
  dismissedJiraSuccess,
  onDismissJiraSuccess,
  githubError,
  githubSuccess,
  dismissedGitHubSuccess,
  onDismissGitHubSuccess,
}: CollectorNotificationsProps): JSX.Element | null {
  const hasNotification =
    jiraError || (jiraSuccess && !dismissedJiraSuccess) ||
    githubError || (githubSuccess && !dismissedGitHubSuccess);

  if (!hasNotification) return null;

  return (
    <>
      {jiraError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-red/10 border-score-red/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-red">Failed to collect metrics</p>
              <p className="text-sm mt-1 text-score-red/80">
                {jiraError.message || 'An unknown error occurred'}
              </p>
              {jiraError.message?.includes('authentication') && (
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

      {jiraSuccess && !dismissedJiraSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-green/10 border-score-green/30">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-score-green">
                Jira metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={onDismissJiraSuccess}
                className="text-score-green hover:text-score-green/70"
              >
                <X className="w-5 h-5" />
              </button>
            </CardContent>
          </Card>
        </>
      )}

      {githubError && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-red/10 border-score-red/30">
            <CardContent className="pt-6">
              <p className="font-medium text-score-red">Failed to collect GitHub metrics</p>
              <p className="text-sm mt-1 text-score-red/80">
                {githubError.message || 'An unknown error occurred'}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      {githubSuccess && !dismissedGitHubSuccess && (
        <>
          <Separator className="my-6" />
          <Card className="bg-score-green/10 border-score-green/30">
            <CardContent className="pt-6 flex items-center justify-between">
              <span className="text-score-green">
                GitHub metrics collected successfully! Scores are being calculated...
              </span>
              <button
                onClick={onDismissGitHubSuccess}
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
