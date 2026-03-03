import { useState } from 'react';
import { downloadBlob } from '@/utils/file';

interface UseDownloadReturn {
  run: (fetchBlob: () => Promise<Blob>, filename: string) => Promise<void>;
  isDownloading: boolean;
  error: string | null;
}

export function useDownload(): UseDownloadReturn {
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fetchBlob: () => Promise<Blob>, filename: string): Promise<void> => {
    setIsDownloading(true);
    setError(null);
    try {
      const blob = await fetchBlob();
      downloadBlob(blob, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsDownloading(false);
    }
  };

  return { run, isDownloading, error };
}
