import { useState } from 'react';
import { isoApi } from '../services/api';
import { downloadBlob } from '../utils/file';

interface UseIsoExportReturn {
  exportSnapshots: (from: string, to: string) => Promise<void>;
  exportSnapshot: (id: string, capturedAt: string) => Promise<void>;
  isExporting: boolean;
  error: string | null;
}

export function useIsoExport(): UseIsoExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportSnapshots = async (from: string, to: string): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const blob = await isoApi.exportSnapshots(from, to);
      downloadBlob(blob, `iso_access_review_${from}_${to}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportSnapshot = async (
    id: string,
    capturedAt: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const blob = await isoApi.exportSnapshot(id);
      const dateStr = capturedAt.slice(0, 10);
      downloadBlob(blob, `iso_access_review_${dateStr}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return { exportSnapshots, exportSnapshot, isExporting, error };
}
