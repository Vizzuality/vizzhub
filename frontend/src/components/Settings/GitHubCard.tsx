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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Eye, EyeOff, Loader2, AlertTriangle } from 'lucide-react';
import { integrationsApi } from '@/services/api/integrations';
import { queryKeys } from '@/hooks/queryKeys';
import type { ProviderStatus } from '@/services/api/integrations';

interface GitHubCardProps {
  readonly status?: ProviderStatus;
}

interface ExpiryInfo {
  text: string;
  level: 'ok' | 'warning' | 'critical';
}

function getExpiryInfo(expiresAt: string | null): ExpiryInfo | null {
  if (!expiresAt) return null;
  const now = new Date();
  const expires = new Date(expiresAt);
  const daysLeft = Math.ceil(
    (expires.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (daysLeft <= 0) return { text: 'Expired', level: 'critical' };
  if (daysLeft <= 7) return { text: `Expires in ${daysLeft} days`, level: 'critical' };
  if (daysLeft <= 30) return { text: `Expires in ${daysLeft} days`, level: 'warning' };
  if (daysLeft <= 60) return { text: `Expires in ${daysLeft} days`, level: 'ok' };
  const months = Math.floor(daysLeft / 30);
  return { text: `Expires in ${months} month${months > 1 ? 's' : ''}`, level: 'ok' };
}

export default function GitHubCard({ status }: GitHubCardProps): JSX.Element {
  const queryClient = useQueryClient();
  const [token, setToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const saveToken = useMutation({
    mutationFn: (pat: string) => integrationsApi.saveGitHubToken(pat),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
      setToken('');
    },
  });

  const deleteToken = useMutation({
    mutationFn: () => integrationsApi.deleteGitHub(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
      setDisconnectOpen(false);
    },
  });

  const handleSave = (): void => {
    if (token.trim()) {
      saveToken.mutate(token.trim());
    }
  };

  const handleDisconnect = (e: React.MouseEvent): void => {
    e.preventDefault();
    deleteToken.mutate();
  };

  const expiryInfo = status?.connected ? getExpiryInfo(status.expires_at) : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>GitHub</CardTitle>
            <CardDescription>
              Configure a Personal Access Token to collect GitHub metrics.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {expiryInfo && expiryInfo.level !== 'ok' && (
              <Badge
                variant={expiryInfo.level === 'critical' ? 'destructive' : 'outline'}
                className={
                  expiryInfo.level === 'warning'
                    ? 'border-yellow-500 text-yellow-600'
                    : ''
                }
              >
                <AlertTriangle className="h-3 w-3 mr-1" />
                {expiryInfo.text}
              </Badge>
            )}
            <Badge variant={status?.connected ? 'default' : 'secondary'}>
              {status?.connected ? 'Connected' : 'Not connected'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {status?.connected && expiryInfo?.level === 'ok' && (
          <div className="text-sm text-muted-foreground">{expiryInfo.text}</div>
        )}

        <div className="space-y-2">
          <Label htmlFor="github-token">
            {status?.connected ? 'Update Token' : 'Personal Access Token'}
          </Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                id="github-token"
                type={showToken ? 'text' : 'password'}
                placeholder="ghp_..."
                value={token}
                onChange={(e) => setToken(e.target.value)}
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
              onClick={handleSave}
              disabled={!token.trim() || saveToken.isPending}
            >
              {saveToken.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                'Save'
              )}
            </Button>
          </div>
        </div>

        {status?.connected && (
          <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                Disconnect
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Disconnect GitHub?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will remove the GitHub token. Metric collection from GitHub
                  will stop until you add a new token.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDisconnect}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteToken.isPending ? 'Disconnecting...' : 'Disconnect'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </CardContent>
    </Card>
  );
}
