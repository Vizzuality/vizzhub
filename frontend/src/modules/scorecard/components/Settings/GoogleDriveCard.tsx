import { useState, useEffect } from 'react';
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
import { useDriveConfig, useDisconnectDrive } from '@/modules/iso/hooks/useIso';
import { useDriveExportStatus, useSaveDriveFolder } from '@/modules/iso-docs/hooks/useDriveExport';

export default function GoogleDriveCard(): JSX.Element {
  const { data: config } = useDriveConfig();
  const { data: exportStatus } = useDriveExportStatus();
  const disconnect = useDisconnectDrive();
  const saveFolder = useSaveDriveFolder();
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [folderId, setFolderId] = useState('');

  useEffect(() => {
    if (exportStatus?.root_folder_id) {
      setFolderId(exportStatus.root_folder_id);
    }
  }, [exportStatus?.root_folder_id]);

  const handleConnect = (): void => {
    globalThis.location.href = '/api/iso/config/google-drive/authorize';
  };

  const handleDisconnect = (e: React.MouseEvent): void => {
    e.preventDefault();
    disconnect.mutate(undefined, {
      onSettled: () => setDisconnectOpen(false),
    });
  };

  const handleSaveFolder = (): void => {
    const trimmed = folderId.trim();
    if (trimmed) {
      saveFolder.mutate(trimmed);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Google Drive</CardTitle>
            <CardDescription>
              Connect Google Drive to export ISO documentation as Google Docs,
              maintaining the folder structure.
            </CardDescription>
          </div>
          <Badge variant={config?.connected ? 'default' : 'secondary'}>
            {config?.connected ? 'Connected' : 'Not connected'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          OAuth connection — authorized once via Google. Grants Drive access to
          create and update the exported Google Docs in the Shared Drive folder
          below.
        </p>
        {config?.connected && (
          <div className="space-y-2">
            <Label htmlFor="drive-folder-id">Shared Drive folder ID</Label>
            <div className="flex gap-2">
              <Input
                id="drive-folder-id"
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                placeholder="e.g. 0AJ8Kx..."
                className="font-mono text-sm"
              />
              <Button
                onClick={handleSaveFolder}
                disabled={!folderId.trim() || saveFolder.isPending}
                variant="outline"
              >
                {saveFolder.isPending ? 'Saving...' : 'Save'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              The folder ID from a Shared Drive where ISO docs will be exported.
              Find it in the folder URL after <span className="font-mono">/folders/</span>.
            </p>
            {exportStatus?.exported_doc_count ? (
              <p className="text-xs text-muted-foreground">
                {exportStatus.exported_doc_count} documents exported
                {exportStatus.last_export_at && (
                  <> &middot; Last export: {new Date(exportStatus.last_export_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</>
                )}
              </p>
            ) : null}
          </div>
        )}
        <div className="flex gap-2">
          {!config?.connected && (
            <Button onClick={handleConnect}>
              Connect Google Drive
            </Button>
          )}
          {config?.connected && (
            <AlertDialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">Disconnect</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Disconnect Google Drive?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will remove the Google Drive connection. Existing files
                    in Drive will not be deleted, but you will not be able to
                    export new updates until you reconnect.
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
