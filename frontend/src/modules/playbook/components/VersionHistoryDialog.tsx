import { VersionHistoryDialog as SharedVersionHistoryDialog } from '@/shared/components/doc/VersionHistoryDialog';
import { usePlaybookVersions, usePlaybookVersion } from '../hooks/usePlaybookVersions';
import { useState, useCallback } from 'react';

interface PlaybookVersionHistoryDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly nodeId: string | null;
  readonly currentVersion: number;
  readonly onRestore: (content: string) => void;
  readonly isRestoring: boolean;
}

export function VersionHistoryDialog({
  open,
  onOpenChange,
  nodeId,
  currentVersion,
  onRestore,
  isRestoring,
}: PlaybookVersionHistoryDialogProps): JSX.Element {
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const { data: versions } = usePlaybookVersions(open ? nodeId : null);
  const { data: versionDetail } = usePlaybookVersion(
    selectedVersion !== null ? nodeId : null,
    selectedVersion,
  );

  const fetchVersion = useCallback(
    (version: number) => {
      if (version !== selectedVersion) {
        setSelectedVersion(version);
        return undefined;
      }
      return versionDetail;
    },
    [selectedVersion, versionDetail],
  );

  const handleOpenChange = (v: boolean): void => {
    onOpenChange(v);
    if (!v) setSelectedVersion(null);
  };

  return (
    <SharedVersionHistoryDialog
      open={open}
      onOpenChange={handleOpenChange}
      versions={versions}
      currentVersion={currentVersion}
      onRestore={onRestore}
      isRestoring={isRestoring}
      fetchVersion={fetchVersion}
    />
  );
}
