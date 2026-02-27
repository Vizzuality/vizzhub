import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { queryKeys } from '@/hooks/queryKeys';
import api from '@/services/api/client';
import type { ProviderStatus } from '@/services/api/integrations';

interface JiraCardProps {
  readonly status?: ProviderStatus;
}

export default function JiraCard({ status }: JiraCardProps): JSX.Element {
  const queryClient = useQueryClient();
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const disconnect = useMutation({
    mutationFn: async () => {
      await api.delete('/oauth/jira/disconnect');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
      setDisconnectOpen(false);
    },
  });

  const handleConnect = (): void => {
    globalThis.location.href = '/api/oauth/jira/authorize';
  };

  const handleDisconnect = (e: React.MouseEvent): void => {
    e.preventDefault();
    disconnect.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Jira</CardTitle>
            <CardDescription>
              Connect your Jira instance to collect project metrics automatically.
            </CardDescription>
          </div>
          <Badge variant={status?.connected ? 'default' : 'secondary'}>
            {status?.connected ? 'Connected' : 'Not connected'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {status?.connected && status.site_url && (
          <div className="text-sm">
            <span className="text-muted-foreground">Site: </span>
            <span className="font-medium">{status.site_url}</span>
          </div>
        )}
        <div className="flex gap-2">
          {!status?.connected && (
            <Button onClick={handleConnect}>Connect Jira</Button>
          )}
          {status?.connected && (
            <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">Disconnect</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Disconnect Jira?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will remove the Jira connection. Metric collection
                    will stop until you reconnect.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDisconnect}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {disconnect.isPending ? 'Disconnecting...' : 'Disconnect'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
