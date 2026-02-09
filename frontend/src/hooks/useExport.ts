import { useState } from 'react';
import { exportsApi } from '../services/api/exports';
import type { ExportParams } from '../services/api/exports';

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function formatApiPeriod(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

interface UseExportReturn {
  exportProject: (
    projectId: string,
    projectName: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ) => Promise<void>;
  exportGlobal: (
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ) => Promise<void>;
  isExporting: boolean;
  error: string | null;
}

export function useExport(): UseExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runExport = async (
    fetchBlob: (params: ExportParams) => Promise<Blob>,
    filename: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const start = formatApiPeriod(fromYear, fromMonth);
      const end = formatApiPeriod(toYear, toMonth);
      const params: ExportParams = { start, end, snapshotType };
      const blob = await fetchBlob(params);
      downloadBlob(blob, filename.replace('{start}', start).replace('{end}', end));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportProject = async (
    projectId: string,
    projectName: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    const safeName = projectName.replaceAll(/[^\w\s-]/g, '').replaceAll(/\s+/g, '_');
    await runExport(
      (params) => exportsApi.exportProjectDetail(projectId, params),
      `${safeName}_scorecard_{start}_{end}.xlsx`,
      fromYear, fromMonth, toYear, toMonth, snapshotType,
    );
  };

  const exportGlobal = async (
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    await runExport(
      (params) => exportsApi.exportGlobalDashboard(params),
      'global_scorecard_{start}_{end}.xlsx',
      fromYear, fromMonth, toYear, toMonth, snapshotType,
    );
  };

  return { exportProject, exportGlobal, isExporting, error };
}
