import { useAllJobs } from '../../hooks/useJobs';
import { useProjects } from '../../hooks/useProjects';
import { formatRelativeTime } from '../../utils/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import type { JobStatus as JobStatusType } from '../../types';

function getStatusBadge(status: JobStatusType): JSX.Element {
  const config: Record<JobStatusType, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
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

export default function JobsTab(): JSX.Element {
  const { data: jobs, isLoading: jobsLoading } = useAllJobs();
  const { data: projects } = useProjects();

  const projectMap = new Map(projects?.map((p) => [p.id, p.name]) ?? []);

  if (jobsLoading) {
    return <LoadingSpinner />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Background Jobs</CardTitle>
      </CardHeader>
      <CardContent>
        {!jobs || jobs.length === 0 ? (
          <p className="text-muted-foreground text-sm">No jobs have been created yet.</p>
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
                    <td className="py-3 pr-4">{getStatusBadge(job.status)}</td>
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
