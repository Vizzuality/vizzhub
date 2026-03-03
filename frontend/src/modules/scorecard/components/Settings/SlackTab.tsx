import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
import { SlackChannelCombobox } from '@/shared/components/ui/SlackChannelCombobox';
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
import { queryKeys } from '@/core/hooks/queryKeys';
import type { SlackChannel } from '@/core/types/project';

interface SlackTabProps {
  readonly status?: ProviderStatus;
  readonly slackSettings?: { leadership_channel_id: string | null };
}

export default function SlackTab({ status, slackSettings }: SlackTabProps): JSX.Element {
  const queryClient = useQueryClient();
  const [botToken, setBotToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<string>('');
  const [testResult, setTestResult] = useState<SlackTestResult | null>(null);
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const { data: channels, isLoading: channelsLoading } = useQuery<SlackChannel[]>({
    queryKey: queryKeys.integrations.slackChannels,
    queryFn: integrationsApi.getSlackChannels,
    enabled: status?.connected ?? false,
  });

  const saveToken = useMutation({
    mutationFn: (token: string) => integrationsApi.saveSlackToken(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.slackChannels });
      setBotToken('');
      setTestResult(null);
    },
  });

  const saveChannel = useMutation({
    mutationFn: (channelId: string) =>
      integrationsApi.updateSlackSettings({ leadership_channel_id: channelId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
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
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
      setDisconnectOpen(false);
      setTestResult(null);
    },
  });

  const handleSaveToken = (): void => {
    if (botToken.trim()) {
      saveToken.mutate(botToken.trim());
    }
  };

  const handleSaveChannel = (): void => {
    if (selectedChannel) {
      saveChannel.mutate(selectedChannel);
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
        </div>

        {/* Test Connection & Channel Config (only when connected) */}
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

            {/* Leadership Channel */}
            <div className="space-y-2">
              <Label>Leadership Channel</Label>
              <p className="text-sm text-muted-foreground">
                Select the channel where business alerts (budget, timeline, overdue)
                will be sent.
              </p>
              <div className="flex items-center gap-2">
                <Label className="text-sm text-muted-foreground">Current:</Label>
                {slackSettings?.leadership_channel_id ? (
                  <Badge variant="secondary">
                    #
                    {channels?.find(
                      (c) => c.id === slackSettings.leadership_channel_id,
                    )?.name || slackSettings.leadership_channel_id}
                  </Badge>
                ) : (
                  <span className="text-sm text-muted-foreground">Not set</span>
                )}
              </div>

              <div className="flex gap-2">
                <SlackChannelCombobox
                  value={selectedChannel}
                  onValueChange={setSelectedChannel}
                  channels={channels ?? []}
                  disabled={channelsLoading}
                  placeholder={channelsLoading ? 'Loading...' : 'Select channel'}
                  className="w-[300px]"
                />
                <Button
                  onClick={handleSaveChannel}
                  disabled={!selectedChannel || saveChannel.isPending}
                >
                  {saveChannel.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Save'
                  )}
                </Button>
              </div>

              {slackSettings?.leadership_channel_id && (
                <p className="text-sm text-muted-foreground">
                  For private channels, make sure to invite the bot:{' '}
                  <code>/invite @Peek</code>
                </p>
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
