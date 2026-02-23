import { useState } from 'react';
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
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ErrorBanner } from '@/components/ui/error-banner';
import { useIsoConfig, useDisconnectGoogleWorkspace } from '@/hooks/useIso';

export default function ISOConfig(): JSX.Element {
  const { data: config, isLoading, error } = useIsoConfig();
  const disconnect = useDisconnectGoogleWorkspace();
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const handleConnect = (): void => {
    const domain = prompt('Enter your Google Workspace domain (e.g. example.com):');
    if (domain) {
      window.location.href =
        `/api/iso/config/google-workspace/authorize?domain=${encodeURIComponent(domain)}`;
    }
  };

  const handleDisconnect = (e: React.MouseEvent): void => {
    e.preventDefault();
    disconnect.mutate(undefined, {
      onSettled: () => {
        setDisconnectOpen(false);
      },
    });
  };

  if (isLoading) {
    return <LoadingSpinner className="py-12" />;
  }

  if (error) {
    return <ErrorBanner message="Failed to load configuration status." />;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Google Workspace</CardTitle>
              <CardDescription>
                Connect your Google Workspace domain to capture access snapshots
                for ISO 27001 compliance reviews.
              </CardDescription>
            </div>
            <Badge variant={config?.connected ? 'default' : 'secondary'}>
              {config?.connected ? 'Connected' : 'Not connected'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {config?.connected && config.domain && (
            <div className="text-sm">
              <span className="text-muted-foreground">Domain: </span>
              <span className="font-medium">{config.domain}</span>
            </div>
          )}
          <div className="flex gap-2">
            {!config?.connected && (
              <Button onClick={handleConnect}>
                Connect Google Workspace
              </Button>
            )}
            {config?.connected && (
              <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive">
                    Disconnect
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Disconnect Google Workspace?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will remove the Google Workspace connection. You will no
                      longer be able to capture new access snapshots until you
                      reconnect. Existing snapshots and reviews will not be deleted.
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
    </div>
  );
}
