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
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function formatPeriod(year: number, month: number): string {
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

  const exportProject = async (
    projectId: string,
    projectName: string,
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const start = formatPeriod(fromYear, fromMonth);
      const end = formatPeriod(toYear, toMonth);
      const params: ExportParams = { start, end, snapshotType };
      const blob = await exportsApi.exportProjectDetail(projectId, params);
      const safeName = projectName.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
      downloadBlob(blob, `${safeName}_scorecard_${start}_${end}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportGlobal = async (
    fromYear: number,
    fromMonth: number,
    toYear: number,
    toMonth: number,
    snapshotType: string,
  ): Promise<void> => {
    setIsExporting(true);
    setError(null);
    try {
      const start = formatPeriod(fromYear, fromMonth);
      const end = formatPeriod(toYear, toMonth);
      const params: ExportParams = { start, end, snapshotType };
      const blob = await exportsApi.exportGlobalDashboard(params);
      downloadBlob(blob, `global_scorecard_${start}_${end}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return { exportProject, exportGlobal, isExporting, error };
}
