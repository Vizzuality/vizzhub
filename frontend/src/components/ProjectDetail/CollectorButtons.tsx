import { RefreshCw, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ProjectStatus } from '../../types';

interface CollectorButtonsProps {
  jiraProjectKey: string | null | undefined;
  githubRepo: string | null | undefined;
  projectStatus: ProjectStatus;
  onCollectJira: () => Promise<unknown>;
  onCollectGitHub: () => Promise<unknown>;
  isCollectingJira: boolean;
  isCollectingGitHub: boolean;
  lastCollectedAt: string | null | undefined;
}

export default function CollectorButtons({
  jiraProjectKey,
  githubRepo,
  projectStatus,
  onCollectJira,
  onCollectGitHub,
  isCollectingJira,
  isCollectingGitHub,
  lastCollectedAt,
}: CollectorButtonsProps): JSX.Element | null {
  if (!jiraProjectKey && !githubRepo) {
    return null;
  }

  const isFinished = projectStatus === 'finished';

  return (
    <div className="flex items-center gap-4">
      <div className="flex gap-2">
        {jiraProjectKey && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    onClick={onCollectJira}
                    disabled={isCollectingJira || isFinished}
                    variant="outline"
                  >
                    <RefreshCw
                      className={cn('w-4 h-4 mr-2', isCollectingJira && 'animate-spin')}
                    />
                    {isCollectingJira ? 'Collecting Jira...' : 'Collect Jira'}
                  </Button>
                </span>
              </TooltipTrigger>
              {isFinished && (
                <TooltipContent>
                  <p>Collectors disabled for finished projects</p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}
        {githubRepo && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    onClick={onCollectGitHub}
                    disabled={isCollectingGitHub || isFinished}
                    variant="outline"
                  >
                    <Github
                      className={cn('w-4 h-4 mr-2', isCollectingGitHub && 'animate-spin')}
                    />
                    {isCollectingGitHub ? 'Collecting GitHub...' : 'Collect GitHub'}
                  </Button>
                </span>
              </TooltipTrigger>
              {isFinished && (
                <TooltipContent>
                  <p>Collectors disabled for finished projects</p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      {lastCollectedAt && (
        <span className="text-sm text-muted-foreground">
          Last collected: {new Date(lastCollectedAt).toLocaleString()}
        </span>
      )}
    </div>
  );
}
