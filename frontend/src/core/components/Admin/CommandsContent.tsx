import { useMemo, useState } from 'react';
import {
  AlertCircle,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  ListTodo,
  X,
  XCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useApproveCommand, useCommands, useRejectCommand } from '@/core/hooks/useCommands';
import { useUserSummaries } from '@/core/hooks/useUsers';
import type { Command } from '@/core/services/commands';
import { formatRelativeTime } from '@/utils/dateUtils';
import { getFullName } from '@/utils/formatters';

const STATUS_FILTERS = [
  { value: 'pending', label: 'Pending' },
  { value: 'executed', label: 'Executed' },
  { value: 'failed', label: 'Failed' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'all', label: 'All' },
] as const;

function StatusBadge({ status }: { readonly status: Command['status'] }): JSX.Element {
  const config: Record<
    Command['status'],
    { icon: JSX.Element; label: string; className: string }
  > = {
    pending: {
      icon: <Clock className="h-3 w-3" />,
      label: 'Pending',
      className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    },
    approved: {
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
      label: 'Approved',
      className: 'bg-blue-100 text-blue-800 border-blue-200',
    },
    executed: {
      icon: <CheckCircle className="h-3 w-3" />,
      label: 'Executed',
      className: 'bg-green-100 text-green-800 border-green-200',
    },
    failed: {
      icon: <AlertCircle className="h-3 w-3" />,
      label: 'Failed',
      className: 'bg-red-100 text-red-800 border-red-200',
    },
    rejected: {
      icon: <XCircle className="h-3 w-3" />,
      label: 'Rejected',
      className: 'bg-gray-100 text-gray-700 border-gray-200',
    },
  };
  const { icon, label, className } = config[status];
  return (
    <Badge variant="outline" className={`flex items-center gap-1 ${className}`}>
      {icon}
      {label}
    </Badge>
  );
}

interface CommandRowProps {
  readonly command: Command;
  readonly userName: string;
  readonly onApprove: (id: string) => void;
  readonly onReject: (id: string) => void;
  readonly isMutating: boolean;
}

function CommandRow({
  command,
  userName,
  onApprove,
  onReject,
  isMutating,
}: CommandRowProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const canAct = command.status === 'pending';

  return (
    <>
      <tr
        className="border-b last:border-b-0 hover:bg-muted/50 cursor-pointer"
        onClick={() => setIsExpanded((prev) => !prev)}
      >
        <td className="py-3 pr-4 w-6">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="py-3 pr-4">
          <Badge variant="secondary">{command.module}</Badge>
        </td>
        <td className="py-3 pr-4 font-mono text-sm">{command.action}</td>
        <td className="py-3 pr-4 text-sm max-w-[400px] truncate" title={command.summary}>
          {command.summary}
        </td>
        <td className="py-3 pr-4 text-sm text-muted-foreground">{userName}</td>
        <td className="py-3 pr-4 text-sm text-muted-foreground">
          {command.requested_at ? formatRelativeTime(command.requested_at) : '-'}
        </td>
        <td className="py-3 pr-4">
          <StatusBadge status={command.status} />
        </td>
        <td className="py-3">
          {canAct && (
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                disabled={isMutating}
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove(command.id);
                }}
                title="Approve"
              >
                <Check className="h-4 w-4 text-green-600" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={isMutating}
                onClick={(e) => {
                  e.stopPropagation();
                  onReject(command.id);
                }}
                title="Reject"
              >
                <X className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr className="bg-muted/30">
          <td colSpan={8} className="p-0">
            <div className="px-6 py-4 border-b space-y-3 text-sm">
              {command.target && (
                <div>
                  <span className="text-muted-foreground">Target:</span>{' '}
                  <span className="font-mono">{command.target}</span>
                </div>
              )}
              <div>
                <p className="text-muted-foreground mb-1">Payload:</p>
                <pre className="bg-background border rounded p-3 text-xs overflow-x-auto">
                  {JSON.stringify(command.payload, null, 2)}
                </pre>
              </div>
              {command.result && (
                <div>
                  <p className="text-muted-foreground mb-1">Result:</p>
                  <pre className="bg-background border rounded p-3 text-xs overflow-x-auto">
                    {JSON.stringify(command.result, null, 2)}
                  </pre>
                </div>
              )}
              {command.error && (
                <div>
                  <p className="text-destructive mb-1">Error:</p>
                  <pre className="bg-destructive/10 border border-destructive/20 rounded p-3 text-xs overflow-x-auto text-destructive">
                    {command.error}
                  </pre>
                </div>
              )}
              {command.reviewed_at && (
                <div className="text-muted-foreground text-xs">
                  Reviewed {formatRelativeTime(command.reviewed_at)}
                  {command.executed_at &&
                    ` · Executed ${formatRelativeTime(command.executed_at)}`}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function CommandsContent(): JSX.Element {
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const { data: commands, isLoading } = useCommands(
    statusFilter === 'all' ? {} : { status: statusFilter },
  );
  const { data: users } = useUserSummaries();
  const approve = useApproveCommand();
  const reject = useRejectCommand();

  const userMap = useMemo(() => {
    const map = new Map<string, string>();
    users?.forEach((u) => {
      map.set(u.id, getFullName(u.first_name, u.last_name, u.email));
    });
    return map;
  }, [users]);

  const isMutating = approve.isPending || reject.isPending;

  const renderBody = (): JSX.Element => {
    if (isLoading) return <LoadingSpinner />;
    if (!commands || commands.length === 0) {
      return <p className="text-muted-foreground text-sm">No commands found.</p>;
    }
    return (
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-sm text-muted-foreground border-b">
              <th className="pb-3 w-6" />
              <th className="pb-3 pr-4 font-medium">Module</th>
              <th className="pb-3 pr-4 font-medium">Action</th>
              <th className="pb-3 pr-4 font-medium">Summary</th>
              <th className="pb-3 pr-4 font-medium">Requested by</th>
              <th className="pb-3 pr-4 font-medium">Requested</th>
              <th className="pb-3 pr-4 font-medium">Status</th>
              <th className="pb-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {commands.map((cmd) => (
              <CommandRow
                key={cmd.id}
                command={cmd}
                userName={userMap.get(cmd.requested_by) ?? cmd.requested_by.slice(0, 8)}
                onApprove={(id) => approve.mutate(id)}
                onReject={(id) => reject.mutate(id)}
                isMutating={isMutating}
              />
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-6 mt-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ListTodo className="h-5 w-5" />
            Command Queue
          </CardTitle>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>{renderBody()}</CardContent>
      </Card>
    </div>
  );
}
