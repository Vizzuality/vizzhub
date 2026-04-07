import { useState, useMemo } from 'react';
import { Download, Copy } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import api from '@/core/services/client';
import type { WidgetProps } from '../index';
import { ScorecardTable } from './ScorecardTable';
import { useKpiDashboard } from './useKpiDashboard';
import { useCopyYear } from '../../../hooks/useRegistryRows';

function getCurrentCycleYear(): number {
  const now = new Date();
  return now.getMonth() >= 2 ? now.getFullYear() : now.getFullYear() - 1;
}

export default function KpiDashboard({ nodeId, isEditor }: WidgetProps): React.ReactElement {
  const [selectedYear, setSelectedYear] = useState(getCurrentCycleYear);
  const [exporting, setExporting] = useState(false);

  const { months, metricsByPeriod, config, manualRows, availableYears, isLoading } =
    useKpiDashboard(nodeId, selectedYear);

  const copyYear = useCopyYear(nodeId);

  const yearOptions = useMemo(() => {
    const yearSet = new Set([...availableYears, selectedYear]);
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [availableYears, selectedYear]);

  async function handleExportXlsx(): Promise<void> {
    const response = await api.get(
      `/iso-docs/widgets/${nodeId}/export`,
      { params: { year: selectedYear, format: 'xlsx' }, responseType: 'blob' },
    );
    const url = URL.createObjectURL(response.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kpi_dashboard_${selectedYear}-${selectedYear + 1}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExportDrive(): Promise<void> {
    setExporting(true);
    try {
      await api.post(
        `/iso-docs/widgets/${nodeId}/export-drive`,
        null,
        { params: { year: selectedYear } },
      );
    } finally {
      setExporting(false);
    }
  }

  function handleCopyFromPrevious(): void {
    copyYear.mutate({ sourceYear: selectedYear - 1, targetYear: selectedYear });
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-muted-foreground">Loading KPI data...</div>
    );
  }

  const globalWeights = config?.global_weights ?? {
    time: 0, cost: 0, quality: 0, value: 0,
    satisfaction: 0, flow: 0, engineering: 0, risk: 0,
  };
  const targets = config?.targets ?? ({} as never);
  const hasManualRows = manualRows.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Cycle:</span>
          <Select
            value={String(selectedYear)}
            onValueChange={(v) => setSelectedYear(Number(v))}
          >
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}–{y + 1}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {isEditor && !hasManualRows && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopyFromPrevious}
              disabled={copyYear.isPending}
            >
              <Copy className="h-4 w-4 mr-1" />
              {copyYear.isPending ? 'Copying...' : 'Copy KPIs from previous cycle'}
            </Button>
          )}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={exporting}>
              <Download className="h-4 w-4 mr-2" />
              {exporting ? 'Exporting...' : 'Export'}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleExportXlsx}>
              Excel (.xlsx)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleExportDrive}>
              Google Drive
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <ScorecardTable
        months={months}
        metricsByPeriod={metricsByPeriod}
        globalWeights={globalWeights}
        targets={targets}
        manualRows={manualRows}
        nodeId={nodeId}
        isEditor={isEditor}
        selectedYear={selectedYear}
      />
    </div>
  );
}
