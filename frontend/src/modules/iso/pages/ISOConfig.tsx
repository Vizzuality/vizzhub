import { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
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
} from '@/shared/components/ui/alert-dialog';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { ErrorBanner } from '@/shared/components/ui/error-banner';
import {
  useIsoConfig,
  useDisconnectGoogleWorkspace,
  useGitHubIsoConfig,
  useSaveGitHubOrg,
  useClearGitHubOrg,
} from '@/modules/iso/hooks/useIso';

export default function ISOConfig(): JSX.Element {
  const { data: config, isLoading, error } = useIsoConfig();
  const disconnect = useDisconnectGoogleWorkspace();
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const {
    data: ghConfig,
    isLoading: ghLoading,
    error: ghError,
  } = useGitHubIsoConfig();
  const saveGitHubOrg = useSaveGitHubOrg();
  const clearGitHubOrg = useClearGitHubOrg();
  const [orgNameInput, setOrgNameInput] = useState('');
  const [clearGhOpen, setClearGhOpen] = useState(false);

  const handleConnect = (): void => {
    const domain = prompt('Enter your Google Workspace domain (e.g. example.com):');
    if (domain) {
      globalThis.location.href =
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

  const handleSaveGitHubOrg = (): void => {
    const trimmed = orgNameInput.trim();
    if (!trimmed) return;
    saveGitHubOrg.mutate(trimmed, {
      onSuccess: () => setOrgNameInput(''),
    });
  };

  const handleClearGitHubOrg = (e: React.MouseEvent): void => {
    e.preventDefault();
    clearGitHubOrg.mutate(undefined, {
      onSettled: () => setClearGhOpen(false),
    });
  };

  if (isLoading || ghLoading) {
    return <LoadingSpinner className="py-12" />;
  }

  if (error || ghError) {
    return <ErrorBanner message="Failed to load configuration status." />;
  }

  return (
    <div className="space-y-6">
      {/* Google Workspace Card */}
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

      {/* GitHub Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>GitHub</CardTitle>
              <CardDescription>
                Configure your GitHub organization to capture access snapshots
                for ISO 27001 compliance reviews. Requires a GitHub PAT with{' '}
                <code className="text-xs">read:org</code> and{' '}
                <code className="text-xs">repo</code> scopes.
              </CardDescription>
            </div>
            <Badge variant={ghConfig?.connected ? 'default' : 'secondary'}>
              {ghConfig?.connected ? 'PAT Connected' : 'Not connected'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!ghConfig?.connected && (
            <p className="text-sm text-muted-foreground">
              Set up a GitHub Personal Access Token in{' '}
              <span className="font-medium">Admin &gt; Integrations</span> first.
            </p>
          )}
          {ghConfig?.connected && (
            <>
              {ghConfig.org_name ? (
                <div className="flex items-center gap-4">
                  <div className="text-sm">
                    <span className="text-muted-foreground">Organization: </span>
                    <span className="font-medium">{ghConfig.org_name}</span>
                  </div>
                  <AlertDialog open={clearGhOpen} onOpenChange={setClearGhOpen}>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        Clear
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Clear GitHub organization?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will remove the GitHub org configuration. You will not be
                          able to capture GitHub snapshots until you set it again. The
                          GitHub PAT will not be deleted.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleClearGitHubOrg}>
                          {clearGitHubOrg.isPending ? 'Clearing...' : 'Clear'}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Organization name (e.g. my-org)"
                    value={orgNameInput}
                    onChange={(e) => setOrgNameInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveGitHubOrg();
                    }}
                    className="max-w-xs"
                  />
                  <Button
                    onClick={handleSaveGitHubOrg}
                    disabled={!orgNameInput.trim() || saveGitHubOrg.isPending}
                  >
                    {saveGitHubOrg.isPending ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              )}
              {saveGitHubOrg.isError && (
                <p className="text-sm text-destructive">
                  Failed to save organization name.
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
