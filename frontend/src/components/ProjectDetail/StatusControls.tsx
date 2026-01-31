import { Pencil, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ProjectStatus } from '../../types';

interface StatusControlsProps {
  onEdit: () => void;
  projectStatus: ProjectStatus;
  hasCollectors: boolean;
  onCollectMetrics: () => void;
  isCollecting: boolean;
  lastCollectedAt?: string | null;
  collectorSources: string;
}

export default function StatusControls({
  onEdit,
  projectStatus,
  hasCollectors,
  onCollectMetrics,
  isCollecting,
  lastCollectedAt,
  collectorSources,
}: StatusControlsProps): JSX.Element {
  const isFinished = projectStatus === 'finished';

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-2">
        <Button variant="ghost" onClick={onEdit} className="border border-input">
          <Pencil className="w-5 h-5 mr-2" />
          Edit
        </Button>
        {hasCollectors && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    variant="ghost"
                    onClick={onCollectMetrics}
                    disabled={isCollecting || isFinished}
                    className="border border-input"
                  >
                    <RefreshCw
                      className={cn('w-5 h-5 mr-2', isCollecting && 'animate-spin')}
                    />
                    {isCollecting ? 'Collecting...' : 'Collect Metrics'}
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {isFinished ? (
                  <p>Collectors disabled for finished projects</p>
                ) : (
                  <p>Collect from {collectorSources}</p>
                )}
              </TooltipContent>
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
