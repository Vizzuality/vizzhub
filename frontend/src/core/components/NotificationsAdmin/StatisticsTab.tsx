import { useNotificationStats } from '../../hooks/useNotifications';
import { useScheduledJobs, useTriggerScheduledJob } from '../../hooks/useAlertDefinitions';
import { formatRelativeTime } from '@/utils/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Bell, BarChart3, Clock, Play, Shield } from 'lucide-react';

function getJobStatusBadge(status: string): JSX.Element {
  const config: Record<string, { variant: 'default' | 'destructive' | 'outline'; label: string }> = {
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

export default function StatisticsTab(): JSX.Element {
  const { data: stats, isLoading: statsLoading } = useNotificationStats();
  const { data: scheduledJobs, isLoading: jobsLoading } = useScheduledJobs();
  const triggerJob = useTriggerScheduledJob();

  const handleTriggerJob = async (jobName: string): Promise<void> => {
    await triggerJob.mutateAsync(jobName);
  };

  if (statsLoading || jobsLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alerts This Month</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_this_month ?? 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Vuln Resolution</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.avg_vulnerability_resolution_days != null
                ? `${stats.avg_vulnerability_resolution_days} days`
                : 'N/A'}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Alerts by Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats && Object.keys(stats.by_type).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(stats.by_type).map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-sm">{type}</span>
                    <Badge variant="secondary">{count}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No alerts this month.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Most Alerted Projects
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats && stats.by_project.length > 0 ? (
              <div className="space-y-3">
                {stats.by_project.map((project) => (
                  <div key={project.project_name} className="flex items-center justify-between">
                    <span className="text-sm">{project.project_name}</span>
                    <Badge variant="secondary">{project.count}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No project alerts this month.</p>
            )}
          </CardContent>
        </Card>
      </div>

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
                    <th className="pb-3 font-medium">Stats</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduledJobs.map((job) => (
                    <tr key={job.name} className="border-b last:border-b-0">
                      <td className="py-3 pr-4">
                        <div>
                          <span className="font-medium">{job.name}</span>
                          <p className="text-xs text-muted-foreground">{job.description}</p>
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-sm">{job.schedule}</td>
                      <td className="py-3 pr-4 text-sm">
                        {job.last_run ? formatRelativeTime(job.last_run.started_at) : 'Never'}
                      </td>
                      <td className="py-3 pr-4">
                        {job.last_run ? getJobStatusBadge(job.last_run.status) : <Badge variant="outline">-</Badge>}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {job.last_run ? (
                          <span>
                            {job.last_run.projects_checked} projects, {job.last_run.alerts_sent} alerts
                          </span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="py-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTriggerJob(job.name)}
                          disabled={triggerJob.isPending}
                        >
                          <Play className="h-4 w-4 mr-1" />
                          Run Now
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
