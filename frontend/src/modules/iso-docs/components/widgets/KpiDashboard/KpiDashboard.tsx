import { useState, useMemo } from 'react';
import { Download } from 'lucide-react';
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
import { ManualKpiTable } from './ManualKpiTable';
import { useKpiDashboard } from './useKpiDashboard';

function getCurrentCycleYear(): number {
  const now = new Date();
  // March = month index 2 in JS (0-indexed). If current month >= March, use current year.
  return now.getMonth() >= 2 ? now.getFullYear() : now.getFullYear() - 1;
}

export default function KpiDashboard({ nodeId, isEditor }: WidgetProps): React.ReactElement {
  const [selectedYear, setSelectedYear] = useState(getCurrentCycleYear);

  const { months, metricsByPeriod, config, manualRows, availableYears, isLoading } =
    useKpiDashboard(nodeId, selectedYear);

  const yearOptions = useMemo(() => {
    const yearSet = new Set([...availableYears, selectedYear]);
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [availableYears, selectedYear]);

  async function handleExportXlsx(): Promise<void> {
    const response = await api.get(
      `/iso-docs/widgets/${nodeId}/export?year=${selectedYear}&format=xlsx`,
      { responseType: 'blob' },
    );
    const url = URL.createObjectURL(response.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kpi_dashboard_${selectedYear}-${selectedYear + 1}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-muted-foreground">Loading KPI data...</div>
    );
  }

  const globalWeights = config?.global_weights ?? {
    time: 0,
    cost: 0,
    quality: 0,
    value: 0,
    satisfaction: 0,
    flow: 0,
    engineering: 0,
    risk: 0,
  };
  const targets = config?.targets ?? ({} as never);

  return (
    <div className="space-y-6">
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
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleExportXlsx}>
              Excel (.xlsx)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div>
        <h3 className="text-base font-semibold mb-3">Global Scorecard</h3>
        <ScorecardTable
          months={months}
          metricsByPeriod={metricsByPeriod}
          globalWeights={globalWeights}
          targets={targets}
        />
      </div>

      <ManualKpiTable
        nodeId={nodeId}
        months={months}
        rows={manualRows}
        isEditor={isEditor}
        selectedYear={selectedYear}
      />
    </div>
  );
}
