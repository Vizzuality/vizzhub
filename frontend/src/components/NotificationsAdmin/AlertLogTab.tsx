import { useState } from 'react';
import { useNotifications } from '../../hooks/useNotifications';
import { useProjects } from '../../hooks/useProjects';
import { useAlertDefinitions } from '../../hooks/useAlertDefinitions';
import { formatRelativeTime } from '../../utils/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { NotificationFilters, NotificationStatus } from '../../types';

function getStatusBadge(status: NotificationStatus): JSX.Element {
  const config: Record<NotificationStatus, { variant: 'default' | 'destructive' | 'outline'; label: string }> = {
    sent: { variant: 'default', label: 'Sent' },
    failed: { variant: 'destructive', label: 'Failed' },
    pending: { variant: 'outline', label: 'Pending' },
  };
  const { variant, label } = config[status] ?? { variant: 'outline', label: status };
  return (
    <Badge
      variant={variant}
      className={status === 'sent' ? 'bg-green-100 text-green-800 border-green-200' : ''}
    >
      {label}
    </Badge>
  );
}

export default function AlertLogTab(): JSX.Element {
  const [filters, setFilters] = useState<NotificationFilters>({
    page: 1,
    page_size: 20,
  });

  const { data: notifications, isLoading } = useNotifications(filters);
  const { data: projects } = useProjects();
  const { data: alertDefinitions } = useAlertDefinitions();

  const handleFilterChange = (key: keyof NotificationFilters, value: string | number | undefined): void => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
      page: key === 'page' ? (value as number) : 1,
    }));
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const totalPages = notifications?.pages ?? 0;
  const currentPage = notifications?.page ?? 1;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Alert Log</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="space-y-2">
            <Label htmlFor="project-filter">Project</Label>
            <Select
              value={filters.project_id ?? 'all'}
              onValueChange={(value) => handleFilterChange('project_id', value)}
            >
              <SelectTrigger id="project-filter">
                <SelectValue placeholder="All Projects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Projects</SelectItem>
                {projects?.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="alert-type-filter">Alert Type</Label>
            <Select
              value={filters.alert_definition_id?.toString() ?? 'all'}
              onValueChange={(value) =>
                handleFilterChange('alert_definition_id', value === 'all' ? undefined : parseInt(value, 10))
              }
            >
              <SelectTrigger id="alert-type-filter">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {alertDefinitions?.map((alert) => (
                  <SelectItem key={alert.id} value={alert.id.toString()}>
                    {alert.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="start-date">Start Date</Label>
            <Input
              id="start-date"
              type="date"
              value={filters.start_date ?? ''}
              onChange={(e) => handleFilterChange('start_date', e.target.value || undefined)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="end-date">End Date</Label>
            <Input
              id="end-date"
              type="date"
              value={filters.end_date ?? ''}
              onChange={(e) => handleFilterChange('end_date', e.target.value || undefined)}
            />
          </div>
        </div>

        {!notifications || notifications.items.length === 0 ? (
          <p className="text-muted-foreground text-sm py-4">No notifications found.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-muted-foreground border-b">
                    <th className="pb-3 font-medium">Timestamp</th>
                    <th className="pb-3 font-medium">Project</th>
                    <th className="pb-3 font-medium">Alert Type</th>
                    <th className="pb-3 font-medium">Channel</th>
                    <th className="pb-3 font-medium">Message</th>
                    <th className="pb-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {notifications.items.map((notification) => (
                    <tr key={notification.id} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 text-sm">
                        {formatRelativeTime(notification.sent_at)}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {notification.project_name ?? 'Unknown'}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {notification.alert_name ?? 'Unknown'}
                      </td>
                      <td className="py-3 pr-4 text-sm font-mono text-xs">
                        {notification.channel_id}
                      </td>
                      <td className="py-3 pr-4 text-sm max-w-xs truncate" title={notification.message}>
                        {notification.message}
                      </td>
                      <td className="py-3">{getStatusBadge(notification.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Showing {notifications.items.length} of {notifications.total} notifications
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleFilterChange('page', currentPage - 1)}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleFilterChange('page', currentPage + 1)}
                  disabled={currentPage >= totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
