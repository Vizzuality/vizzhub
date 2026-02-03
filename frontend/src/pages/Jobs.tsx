import { useState } from 'react';
import { useAllJobs, useCancelJob, useDeleteJob } from '../hooks/useJobs';
import { useScheduledJobs, useTriggerScheduledJob } from '../hooks/useAlertDefinitions';
import { useProjects } from '../hooks/useProjects';
import { formatRelativeTime } from '../utils/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  XCircle,
  Trash2,
  Play,
  Clock,
  Briefcase,
  ChevronDown,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import type { JobStatus as JobStatusType, ScheduledJobInfo } from '../types';

function getJobStatusBadge(status: JobStatusType): JSX.Element {
  const config: Record<
    JobStatusType,
    { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }
  > = {
    pending: { variant: 'secondary', label: 'Pending' },
    running: { variant: 'default', label: 'Running' },
    completed: { variant: 'outline', label: 'Completed' },
    failed: { variant: 'destructive', label: 'Failed' },
    cancelled: { variant: 'outline', label: 'Cancelled' },
  };
  const { variant, label } = config[status];
  return (
    <Badge
      variant={variant}
      className={status === 'completed' ? 'bg-green-100 text-green-800 border-green-200' : ''}
    >
      {label}
    </Badge>
  );
}

function getScheduledJobStatusBadge(status: string): JSX.Element {
  const config: Record<string, { variant: 'default' | 'destructive' | 'outline'; label: string }> =
    {
      completed: { variant: 'default', label: 'Completed' },
      running: { variant: 'outline', label: 'Running' },
      failed: { variant: 'destructive', label: 'Failed' },
    };
  const { variant, label } = config[status] ?? { variant: 'outline', label: status };
  return (
    <Badge
      variant={variant}
      className={status === 'completed' ? 'bg-green-100 text-green-800 border-green-200' : ''}
    >
      {label}
    </Badge>
  );
}

interface ScheduledJobRowProps {
  job: ScheduledJobInfo;
  onTrigger: (jobName: string) => Promise<void>;
  isTriggering: boolean;
}

function ScheduledJobRow({ job, onTrigger, isTriggering }: ScheduledJobRowProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const lastRun = job.last_run;
  const hasLastRun = lastRun !== null;

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      <tr className="border-b last:border-b-0 hover:bg-muted/50 cursor-pointer">
        <td className="py-3 pr-4">
          <CollapsibleTrigger asChild>
            <div className="flex items-center gap-2">
              {hasLastRun ? (
                isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )
              ) : (
                <span className="w-4" />
              )}
              <div>
                <span className="font-medium">{job.name}</span>
                <p className="text-xs text-muted-foreground">{job.description}</p>
              </div>
            </div>
          </CollapsibleTrigger>
        </td>
        <td className="py-3 pr-4 text-sm">{job.schedule}</td>
        <td className="py-3 pr-4 text-sm">
          {lastRun ? formatRelativeTime(lastRun.started_at) : 'Never'}
        </td>
        <td className="py-3 pr-4">
          {lastRun ? (
            <div className="flex items-center gap-2">
              {getScheduledJobStatusBadge(lastRun.status)}
              {lastRun.error_message && <AlertCircle className="h-4 w-4 text-destructive" />}
            </div>
          ) : (
            <Badge variant="outline">-</Badge>
          )}
        </td>
        <td className="py-3 pr-4 text-sm text-muted-foreground">{job.schedule}</td>
        <td className="py-3">
          <Button
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onTrigger(job.name);
            }}
            disabled={isTriggering}
          >
            <Play className="h-4 w-4 mr-1" />
            Run Now
          </Button>
        </td>
      </tr>
      {lastRun && (
        <tr>
          <td colSpan={6} className="p-0">
            <CollapsibleContent>
              <div className="bg-muted/30 px-6 py-4 border-b">
                <h4 className="font-medium text-sm mb-3">Last Run Details</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Projects Checked:</span>{' '}
                    <span className="font-medium">{lastRun.projects_checked}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Alerts Sent:</span>{' '}
                    <span className="font-medium">{lastRun.alerts_sent}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Completed:</span>{' '}
                    <span className="font-medium">
                      {lastRun.completed_at
                        ? formatRelativeTime(lastRun.completed_at)
                        : 'In Progress'}
                    </span>
                  </div>
                </div>
                {lastRun.error_message && (
                  <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                      <div>
                        <p className="font-medium text-sm text-destructive">Error Message</p>
                        <p className="text-sm text-muted-foreground">{lastRun.error_message}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CollapsibleContent>
          </td>
        </tr>
      )}
    </Collapsible>
  );
}

function BackgroundJobsSection(): JSX.Element {
  const { data: jobs, isLoading: jobsLoading } = useAllJobs();
  const { data: projects } = useProjects();
  const cancelJob = useCancelJob();
  const deleteJob = useDeleteJob();

  const projectMap = new Map(projects?.map((p) => [p.id, p.name]) ?? []);

  const handleCancel = (jobId: string): void => {
    cancelJob.mutate(jobId);
  };

  const handleDelete = (jobId: string): void => {
    deleteJob.mutate(jobId);
  };

  if (jobsLoading) {
    return <LoadingSpinner />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="h-5 w-5" />
          Background Jobs
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!jobs || jobs.length === 0 ? (
          <p className="text-muted-foreground text-sm">No background jobs have been created yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Name</th>
                  <th className="pb-3 font-medium">Project</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Progress</th>
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="border-b last:border-b-0">
                    <td className="py-3 pr-4">
                      <span className="font-medium">{job.name}</span>
                    </td>
                    <td className="py-3 pr-4 text-sm text-muted-foreground">
                      {job.project_id ? projectMap.get(job.project_id) ?? 'Unknown' : '-'}
                    </td>
                    <td className="py-3 pr-4">{getJobStatusBadge(job.status)}</td>
                    <td className="py-3 pr-4">
                      {job.status === 'running' ? (
                        <div className="flex items-center gap-2">
                          <Progress value={job.progress} className="w-20 h-2" />
                          <span className="text-sm text-muted-foreground">{job.progress}%</span>
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">{job.progress}%</span>
                      )}
                    </td>
                    <td className="py-3 text-sm text-muted-foreground">
                      {formatRelativeTime(job.created_at)}
                    </td>
                    <td className="py-3">
                      <div className="flex gap-1">
                        {job.status === 'pending' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancel(job.id)}
                            disabled={cancelJob.isPending}
                            title="Cancel job"
                          >
                            <XCircle className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        )}
                        {['completed', 'failed', 'cancelled'].includes(job.status) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(job.id)}
                            disabled={deleteJob.isPending}
                            title="Delete job"
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ScheduledJobsSection(): JSX.Element {
  const { data: scheduledJobs, isLoading: jobsLoading } = useScheduledJobs();
  const triggerJob = useTriggerScheduledJob();

  const handleTriggerJob = async (jobName: string): Promise<void> => {
    await triggerJob.mutateAsync(jobName);
  };

  if (jobsLoading) {
    return <LoadingSpinner />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Scheduled Jobs
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!scheduledJobs || scheduledJobs.length === 0 ? (
          <p className="text-muted-foreground text-sm">No scheduled jobs configured.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-muted-foreground border-b">
                  <th className="pb-3 font-medium">Job Name</th>
                  <th className="pb-3 font-medium">Schedule</th>
                  <th className="pb-3 font-medium">Last Run</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Next Run</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {scheduledJobs.map((job) => (
                  <ScheduledJobRow
                    key={job.name}
                    job={job}
                    onTrigger={handleTriggerJob}
                    isTriggering={triggerJob.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function Jobs(): JSX.Element {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Jobs</h1>

      <ScheduledJobsSection />
      <BackgroundJobsSection />
    </div>
  );
}
