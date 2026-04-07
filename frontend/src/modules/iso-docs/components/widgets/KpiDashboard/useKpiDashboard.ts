import { useMemo } from 'react';
import { useGlobalMetricsHistory } from '@/modules/scorecard/hooks/useGlobalMetrics';
import { useScoringConfig } from '@/modules/scorecard/hooks/useScores';
import { useRegistryRows, useRegistryYears } from '../../../hooks/useRegistryRows';
import type { GlobalMetricsRecord, ScoringConfig } from '@/modules/scorecard/types';
import type { RegistryRow } from '../../../types/registry';
import type { IsoCycle, MonthColumn } from './types';
import { getCycleMonths, getIsoCycle } from './constants';

interface KpiDashboardData {
  cycle: IsoCycle;
  months: MonthColumn[];
  metricsByPeriod: Map<string, GlobalMetricsRecord>;
  config: ScoringConfig | undefined;
  manualRows: RegistryRow[];
  availableYears: number[];
  isLoading: boolean;
}

export function periodKey(year: number, month: number): string {
  return `${year}-${month}`;
}

export function useKpiDashboard(nodeId: string, selectedYear: number): KpiDashboardData {
  const cycle = getIsoCycle(selectedYear);
  const months = useMemo(() => getCycleMonths(cycle), [cycle.year]);

  const { data: history, isLoading: historyLoading } = useGlobalMetricsHistory(24);
  const { data: config, isLoading: configLoading } = useScoringConfig();
  const { data: rows, isLoading: rowsLoading } = useRegistryRows(nodeId, selectedYear);
  const { data: years } = useRegistryYears(nodeId);

  const metricsByPeriod = useMemo(() => {
    const map = new Map<string, GlobalMetricsRecord>();
    if (!history) return map;
    for (const record of history) {
      map.set(periodKey(record.period_year, record.period_month), record);
    }
    return map;
  }, [history]);

  const availableYears = useMemo(() => {
    const yearSet = new Set<number>();
    if (history) {
      for (const record of history) {
        if (record.period_month >= 3) {
          yearSet.add(record.period_year);
        } else {
          yearSet.add(record.period_year - 1);
        }
      }
    }
    if (years) {
      for (const y of years) {
        yearSet.add(y);
      }
    }
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [history, years]);

  return {
    cycle,
    months,
    metricsByPeriod,
    config,
    manualRows: rows ?? [],
    availableYears,
    isLoading: historyLoading || configLoading || rowsLoading,
  };
}
