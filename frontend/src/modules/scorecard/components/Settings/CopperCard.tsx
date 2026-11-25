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
import { Loader2 } from 'lucide-react';
import { integrationsApi } from '@/core/services/integrations';
import { invalidateIntegrations } from '@/core/hooks/invalidations';
import { cn } from '@/lib/utils';
import { getApiErrorDetail } from '@/utils/apiErrors';
import type { ProviderStatus } from '@/core/services/integrations';

interface CopperCardProps {
  readonly status?: ProviderStatus;
  readonly userEmail: string | null;
}

const SAVE_ERROR_FALLBACK = 'Could not save the Copper credentials';

interface SaveInput {
  apiKey: string;
  email: string;
}

export default function CopperCard({ status, userEmail }: CopperCardProps): JSX.Element {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState('');
  const [email, setEmail] = useState('');
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const connected = status?.connected ?? false;

  const save = useMutation({
    mutationFn: ({ apiKey: key, email: owner }: SaveInput) =>
      integrationsApi.saveCopperCredentials(key, owner),
    onSuccess: () => {
      invalidateIntegrations(queryClient);
      setApiKey('');
      setEmail('');
    },
  });

  const disconnect = useMutation({
    mutationFn: () => integrationsApi.deleteCopper(),
    onSuccess: () => {
      invalidateIntegrations(queryClient);
      setDisconnectOpen(false);
    },
  });

  const canSave = apiKey.trim() !== '' && email.trim() !== '' && !save.isPending;

  const handleSave = (): void => {
    if (canSave) save.mutate({ apiKey: apiKey.trim(), email: email.trim() });
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
            <CardTitle>Copper</CardTitle>
            <CardDescription>
              Read opportunities and companies from the Copper CRM.
            </CardDescription>
          </div>
          <span className="flex items-center gap-2 text-sm text-foreground">
            <span
              className={cn(
                'inline-block w-2 h-2 rounded-full shrink-0',
                connected ? 'bg-green-500' : 'bg-muted-foreground'
              )}
            />
            {connected ? 'Connected' : 'Not connected'}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {connected && userEmail && (
          <div className="text-sm">
            <span className="text-muted-foreground">Key owner: </span>
            <span className="font-medium">{userEmail}</span>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="copper-api-key">{connected ? 'New API key' : 'API key'}</Label>
            <Input
              id="copper-api-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="copper-user-email">Key owner email</Label>
            <Input
              id="copper-user-email"
              type="email"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          The email must be the one of the Copper user who generated the key. The key is checked
          against Copper before saving and stored encrypted. VizzHub only reads from Copper.
        </p>
        {save.isError && (
          <p className="text-sm text-destructive">
            {getApiErrorDetail(save.error, SAVE_ERROR_FALLBACK)}
          </p>
        )}

        <div className="flex items-center gap-2">
          <Button onClick={handleSave} disabled={!canSave}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
          </Button>
          {connected && (
            <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">Disconnect</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Disconnect Copper?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This removes the stored API key. Importing opportunities from Copper stops
                    until a new key is saved.
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
