import { isoApi } from '../services/iso';
import { useDownload } from '@/core/hooks/useDownload';

interface UseIsoExportReturn {
  exportSnapshots: (from: string, to: string, provider?: string) => Promise<void>;
  exportSnapshot: (id: string, capturedAt: string) => Promise<void>;
  isExporting: boolean;
  error: string | null;
}

export function useIsoExport(): UseIsoExportReturn {
  const { run, isDownloading, error } = useDownload();

  const exportSnapshots = async (from: string, to: string, provider?: string): Promise<void> => {
    const suffix = provider ? `_${provider}` : '';
    await run(
      () => isoApi.exportSnapshots(from, to, provider),
      `iso_access_review${suffix}_${from}_${to}.xlsx`,
    );
  };

  const exportSnapshot = async (
    id: string,
    capturedAt: string,
  ): Promise<void> => {
    const dateStr = capturedAt.slice(0, 10);
    await run(
      () => isoApi.exportSnapshot(id),
      `iso_access_review_${dateStr}.xlsx`,
    );
  };

  return { exportSnapshots, exportSnapshot, isExporting: isDownloading, error };
}
