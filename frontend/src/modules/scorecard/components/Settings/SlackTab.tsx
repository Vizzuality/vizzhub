import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
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
import { CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { integrationsApi } from '@/core/services/integrations';
import type { ProviderStatus, SlackTestResult } from '@/core/services/integrations';
import { invalidateIntegrations } from '@/core/hooks/invalidations';

interface SlackTabProps {
  readonly status?: ProviderStatus;
}

export default function SlackTab({ status }: SlackTabProps): JSX.Element {
  const queryClient = useQueryClient();
  const [botToken, setBotToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [testResult, setTestResult] = useState<SlackTestResult | null>(null);
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const saveToken = useMutation({
    mutationFn: (token: string) => integrationsApi.saveSlackToken(token),
    onSuccess: () => {
      invalidateIntegrations(queryClient);
      setBotToken('');
      setTestResult(null);
    },
  });

  const testConnection = useMutation({
    mutationFn: integrationsApi.testSlackConnection,
    onSuccess: (result) => {
      setTestResult(result);
    },
    onError: () => {
      setTestResult({ ok: false, error: 'Connection failed' });
    },
  });

  const deleteSlack = useMutation({
    mutationFn: () => integrationsApi.deleteSlack(),
    onSuccess: () => {
      invalidateIntegrations(queryClient);
      setDisconnectOpen(false);
      setTestResult(null);
    },
  });

  const handleSaveToken = (): void => {
    if (botToken.trim()) {
      saveToken.mutate(botToken.trim());
    }
  };

  const handleDisconnect = (e: React.MouseEvent): void => {
    e.preventDefault();
    deleteSlack.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Slack</CardTitle>
            <CardDescription>
              Configure a bot token to send notifications. Get this from your Slack
              app's OAuth & Permissions page.
            </CardDescription>
          </div>
          <Badge variant={status?.connected ? 'default' : 'secondary'}>
            {status?.connected ? 'Connected' : 'Not connected'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Bot Token Input */}
        <div className="space-y-2">
          <Label htmlFor="bot-token">
            {status?.connected ? 'Update Bot Token' : 'Bot Token'}
          </Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                id="bot-token"
                type={showToken ? 'text' : 'password'}
                placeholder="xoxb-..."
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => setShowToken(!showToken)}
              >
                {showToken ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
            <Button
              onClick={handleSaveToken}
              disabled={!botToken.trim() || saveToken.isPending}
            >
              {saveToken.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                'Save'
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Bot User OAuth Token (<span className="font-mono">xoxb-…</span>), not a
            user token. Required bot scopes:{' '}
            <span className="font-mono">chat:write</span>,{' '}
            <span className="font-mono">channels:read</span>,{' '}
            <span className="font-mono">users:read.email</span>.
          </p>
        </div>

        {/* Test Connection (only when connected) */}
        {status?.connected && (
          <>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => testConnection.mutate()}
                disabled={testConnection.isPending}
              >
                {testConnection.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Test Connection
              </Button>
              {testResult && (
                <div className="flex items-center gap-2">
                  {testResult.ok ? (
                    <>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      <span className="text-sm text-green-600">
                        Connected to {testResult.team}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-red-600" />
                      <span className="text-sm text-red-600">{testResult.error}</span>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Disconnect */}
            <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  Disconnect
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Disconnect Slack?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will remove the Slack bot token and stop all notifications
                    until you reconnect.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDisconnect}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {deleteSlack.isPending ? 'Disconnecting...' : 'Disconnect'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </>
        )}
      </CardContent>
    </Card>
  );
}
