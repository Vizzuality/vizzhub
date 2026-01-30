import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ProjectStatus } from '../../types';

interface CollectorButtonsProps {
  jiraProjectKey: string | null | undefined;
  githubRepo: string | null | undefined;
  projectStatus: ProjectStatus;
  onCollectMetrics: () => void;
  isCollecting: boolean;
  lastCollectedAt: string | null | undefined;
}

export default function CollectorButtons({
  jiraProjectKey,
  githubRepo,
  projectStatus,
  onCollectMetrics,
  isCollecting,
  lastCollectedAt,
}: CollectorButtonsProps): JSX.Element | null {
  if (!jiraProjectKey && !githubRepo) {
    return null;
  }

  const isFinished = projectStatus === 'finished';
  const sources = [jiraProjectKey && 'Jira', githubRepo && 'GitHub'].filter(Boolean).join(' & ');

  return (
    <div className="flex items-center gap-4">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                onClick={onCollectMetrics}
                disabled={isCollecting || isFinished}
                variant="outline"
              >
                <RefreshCw
                  className={cn('w-4 h-4 mr-2', isCollecting && 'animate-spin')}
                />
                {isCollecting ? 'Collecting...' : 'Collect Metrics'}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {isFinished ? (
              <p>Collectors disabled for finished projects</p>
            ) : (
              <p>Collect from {sources}</p>
            )}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {lastCollectedAt && (
        <span className="text-sm text-muted-foreground">
          Last collected: {new Date(lastCollectedAt).toLocaleString()}
        </span>
      )}
    </div>
  );
}
