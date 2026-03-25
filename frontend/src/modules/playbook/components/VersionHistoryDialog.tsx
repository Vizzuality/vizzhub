import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { PageViewer } from './PageViewer';
import { usePlaybookVersions, usePlaybookVersion } from '../hooks/usePlaybookVersions';
import type { VersionListItem } from '../types/playbook';

interface VersionHistoryDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly nodeId: string | null;
  readonly currentVersion: number;
  readonly onRestore: (content: string) => void;
  readonly isRestoring: boolean;
}

function VersionRow({
  version,
  isCurrent,
  onClick,
}: Readonly<{
  version: VersionListItem;
  isCurrent: boolean;
  onClick: () => void;
}>): JSX.Element {
  return (
    <button
      className="flex items-center justify-between w-full text-left py-2.5 px-3 rounded hover:bg-muted text-sm"
      onClick={onClick}
    >
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="font-medium">v{version.version}</span>
          {version.created_by_name && (
            <span className="text-muted-foreground">{version.created_by_name}</span>
          )}
          {isCurrent && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-accent text-accent-foreground">
              current
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(version.created_at).toLocaleString()}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs font-mono">
        {version.lines_added > 0 && (
          <span className="text-green-600">+{version.lines_added}</span>
        )}
        {version.lines_removed > 0 && (
          <span className="text-red-500">-{version.lines_removed}</span>
        )}
        {version.lines_added === 0 && version.lines_removed === 0 && version.version > 1 && (
          <span className="text-muted-foreground">no changes</span>
        )}
      </div>
    </button>
  );
}

export function VersionHistoryDialog({
  open,
  onOpenChange,
  nodeId,
  currentVersion,
  onRestore,
  isRestoring,
}: VersionHistoryDialogProps): JSX.Element {
  const [previewVersion, setPreviewVersion] = useState<number | null>(null);

  const { data: versions } = usePlaybookVersions(open ? nodeId : null);
  const { data: versionDetail } = usePlaybookVersion(
    previewVersion !== null ? nodeId : null,
    previewVersion,
  );

  const handleOpenChange = (v: boolean): void => {
    onOpenChange(v);
    if (!v) setPreviewVersion(null);
  };

  const isPreview = previewVersion !== null;
  const canRestore = versionDetail && versionDetail.version !== currentVersion;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className={isPreview ? 'max-w-4xl' : 'max-w-lg'}>
        <DialogHeader>
          <DialogTitle>
            {isPreview ? (
              <div className="flex items-center gap-2">
                <button
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setPreviewVersion(null)}
                >
                  &larr;
                </button>
                Version {previewVersion} preview
              </div>
            ) : (
              'Version history'
            )}
          </DialogTitle>
        </DialogHeader>

        {isPreview ? (
          <div className="flex flex-col gap-4">
            <div className="max-h-[60vh] overflow-auto border rounded p-4">
              {versionDetail ? (
                <PageViewer content={versionDetail.content} />
              ) : (
                <p className="text-sm text-muted-foreground">Loading...</p>
              )}
            </div>
            {canRestore && (
              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={() => handleRestore()}
                  disabled={isRestoring}
                >
                  {isRestoring ? 'Restoring...' : `Restore v${previewVersion}`}
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="max-h-96 overflow-auto">
            {versions && versions.length > 0 ? (
              <div className="space-y-1">
                {versions.map((v) => (
                  <VersionRow
                    key={v.version}
                    version={v}
                    isCurrent={v.version === currentVersion}
                    onClick={() => setPreviewVersion(v.version)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No versions yet
              </p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );

  function handleRestore(): void {
    if (!versionDetail) return;
    onRestore(versionDetail.content);
    setPreviewVersion(null);
  }
}
