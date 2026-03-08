import { RefreshCw } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  useIsoConfig,
  useGitHubIsoConfig,
  useCaptureSnapshot,
} from '@/modules/iso/hooks/useIso';

export default function ProviderCaptureButtons(): JSX.Element {
  const { data: gwConfig } = useIsoConfig();
  const { data: ghConfig } = useGitHubIsoConfig();
  const capture = useCaptureSnapshot();

  const gwConnected = gwConfig?.connected ?? false;
  const ghConnected = (ghConfig?.connected ?? false) && !!ghConfig?.org_name;

  return (
    <div className="flex items-center gap-2">
      {gwConnected && (
        <Button
          onClick={() => capture.mutate('google_workspace')}
          disabled={capture.isPending}
          variant="outline"
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`}
          />
          {capture.isPending ? 'Capturing...' : 'Capture Google Workspace'}
        </Button>
      )}
      {ghConnected && (
        <Button
          onClick={() => capture.mutate('github')}
          disabled={capture.isPending}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`}
          />
          {capture.isPending ? 'Capturing...' : 'Capture GitHub'}
        </Button>
      )}
      {!gwConnected && !ghConnected && (
        <p className="text-sm text-muted-foreground">
          No providers configured. Set up a provider in ISO Settings.
        </p>
      )}
    </div>
  );
}
