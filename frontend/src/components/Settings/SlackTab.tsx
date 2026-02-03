import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { slackApi } from '@/services/api';
import { queryKeys } from '@/hooks/queryKeys';
import { SlackChannel } from '@/types';

interface SlackConfig {
  id: number;
  bot_token_configured: boolean;
  leadership_channel_id: string | null;
  created_at: string;
  updated_at: string;
}

interface SlackTestResult {
  ok: boolean;
  team?: string;
  bot_id?: string;
  error?: string;
}

export default function SlackTab(): JSX.Element {
  const queryClient = useQueryClient();
  const [botToken, setBotToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<string>('');
  const [testResult, setTestResult] = useState<SlackTestResult | null>(null);

  const { data: config, isLoading: configLoading } = useQuery<SlackConfig>({
    queryKey: queryKeys.slack.status,
    queryFn: async () => {
      const response = await slackApi.getConfig();
      return response;
    },
  });

  const { data: channels, isLoading: channelsLoading } = useQuery<SlackChannel[]>({
    queryKey: queryKeys.slack.channels,
    queryFn: slackApi.getChannels,
    enabled: config?.bot_token_configured ?? false,
  });

  const updateConfig = useMutation({
    mutationFn: async (data: { bot_token?: string; leadership_channel_id?: string }) => {
      return slackApi.updateConfig(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.slack.status });
      queryClient.invalidateQueries({ queryKey: queryKeys.slack.channels });
      setBotToken('');
      setTestResult(null);
    },
  });

  const testConnection = useMutation({
    mutationFn: slackApi.testConnection,
    onSuccess: (result) => {
      setTestResult(result);
    },
    onError: () => {
      setTestResult({ ok: false, error: 'Connection failed' });
    },
  });

  const handleSaveToken = (): void => {
    if (botToken.trim()) {
      updateConfig.mutate({ bot_token: botToken.trim() });
    }
  };

  const handleSaveChannel = (): void => {
    if (selectedChannel) {
      updateConfig.mutate({ leadership_channel_id: selectedChannel });
    }
  };

  if (configLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Bot Token Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Slack Bot Token</CardTitle>
          <CardDescription>
            Configure the bot token for sending notifications. Get this from your Slack app's OAuth
            & Permissions page.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Label>Status:</Label>
            {config?.bot_token_configured ? (
              <Badge variant="default" className="bg-green-600">
                <CheckCircle className="h-3 w-3 mr-1" />
                Configured
              </Badge>
            ) : (
              <Badge variant="destructive">
                <XCircle className="h-3 w-3 mr-1" />
                Not Configured
              </Badge>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="bot-token">
              {config?.bot_token_configured ? 'Update Bot Token' : 'Bot Token'}
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
                  {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <Button onClick={handleSaveToken} disabled={!botToken.trim() || updateConfig.isPending}>
                {updateConfig.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
              </Button>
            </div>
          </div>

          {config?.bot_token_configured && (
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
          )}
        </CardContent>
      </Card>

      {/* Leadership Channel Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Leadership Channel</CardTitle>
          <CardDescription>
            Select the channel where business alerts (budget, timeline, overdue) will be sent.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!config?.bot_token_configured ? (
            <p className="text-sm text-muted-foreground">
              Configure the bot token first to select a channel.
            </p>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Label>Current:</Label>
                {config?.leadership_channel_id ? (
                  <Badge variant="secondary">
                    #{channels?.find((c) => c.id === config.leadership_channel_id)?.name ||
                      config.leadership_channel_id}
                  </Badge>
                ) : (
                  <span className="text-sm text-muted-foreground">Not set</span>
                )}
              </div>

              <div className="flex gap-2">
                <Select
                  value={selectedChannel}
                  onValueChange={setSelectedChannel}
                  disabled={channelsLoading}
                >
                  <SelectTrigger className="w-[300px]">
                    <SelectValue placeholder={channelsLoading ? 'Loading...' : 'Select channel'} />
                  </SelectTrigger>
                  <SelectContent>
                    {channels?.map((channel) => (
                      <SelectItem key={channel.id} value={channel.id}>
                        #{channel.name} {channel.is_private && '🔒'}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={handleSaveChannel}
                  disabled={!selectedChannel || updateConfig.isPending}
                >
                  {updateConfig.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
                </Button>
              </div>

              {config?.leadership_channel_id && (
                <p className="text-sm text-muted-foreground">
                  For private channels, make sure to invite the bot: <code>/invite @Peek</code>
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
