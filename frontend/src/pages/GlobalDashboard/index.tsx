/**
 * Global Dashboard Page
 *
 * Displays averaged indicators and scores across all projects.
 * Uses batch calculation (stored data only) to allow recalculation with different weights.
 */

import { useState, useMemo, useCallback } from 'react';
import {
  useGlobalMetrics,
  useGlobalMetricsHistory,
  useCalculateGlobalMetrics,
  useRecalculateGlobalMetrics,
} from '../../hooks/useGlobalMetrics';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { MonthYearPicker } from '@/components/ui/month-year-picker';
import { NativeSelect } from '@/components/ui/native-select';
import { Calculator, RefreshCw, Globe, FileDown, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useExport } from '../../hooks/useExport';
import { useAuth } from '@/hooks/useAuth';
import type { Dimension } from '../../types';
import { ALL_DIMENSIONS } from '../../types';
import type { GlobalMetricsRecord } from '../../types/global';
import { useScoreThresholds } from '@/hooks/useConfig';
import { formatPeriod } from '@/utils/formatters';
import { TIMELINE_MONTHS } from './constants';
import type { Period, HistoricalDataPoint } from './types';
import { generateGlobalMonthRange, formatPeriodLabel } from './utils';
import {
  GlobalTimelineChart,
  GlobalScoreCard,
  DimensionBreakdownChart,
  GlobalMetricCard,
} from './components';

export default function GlobalDashboard(): JSX.Element {
  const now = new Date();
  const [selectedPeriod, setSelectedPeriod] = useState<Period>({
    year: now.getFullYear(),
    month: now.getMonth() + 1,
  });
  const [visibleDimensions, setVisibleDimensions] = useState<Set<Dimension>>(
    new Set(ALL_DIMENSIONS),
  );

  const { data: globalMetrics, isLoading } = useGlobalMetrics(
    selectedPeriod.year,
    selectedPeriod.month,
  );
  const { data: history } = useGlobalMetricsHistory(TIMELINE_MONTHS);
  const calculateMutation = useCalculateGlobalMetrics();
  const recalculateMutation = useRecalculateGlobalMetrics();
  const thresholds = useScoreThresholds();
  const { exportGlobal, isExporting, error: exportError } = useExport();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [exportFromYear, setExportFromYear] = useState(now.getFullYear());
  const [exportFromMonth, setExportFromMonth] = useState(1);
  const [exportToYear, setExportToYear] = useState(now.getFullYear());
  const [exportToMonth, setExportToMonth] = useState(now.getMonth() + 1);
  const [exportSnapshotType, setExportSnapshotType] = useState('cumulative');

  const handleExport = async (): Promise<void> => {
    await exportGlobal(
      exportFromYear,
      exportFromMonth,
      exportToYear,
      exportToMonth,
      exportSnapshotType,
    );
  };

  const periods = useMemo(() => generateGlobalMonthRange(TIMELINE_MONTHS), []);

  const getIndicatorHistory = useCallback(
    (indicatorKey: keyof GlobalMetricsRecord['indicators']): HistoricalDataPoint[] => {
      if (!history || history.length < 2) return [];
      return history
        .slice()
        .reverse()
        .map((r) => ({
          period: formatPeriod(r.period_year, r.period_month),
          value: r.indicators[indicatorKey]?.value ?? null,
        }));
    },
    [history],
  );

  const handleToggleDimension = useCallback((dimension: Dimension) => {
    setVisibleDimensions((prev) => {
      const next = new Set(prev);
      if (next.has(dimension)) {
        next.delete(dimension);
      } else {
        next.add(dimension);
      }
      return next;
    });
  }, []);

  const handleCalculateAll = (): void => {
    const startYear = now.getFullYear() - 1;
    calculateMutation.mutate({
      from_year: startYear,
      from_month: now.getMonth() + 1,
      to_year: now.getFullYear(),
      to_month: now.getMonth() + 1,
    });
  };

  const handleRecalculateAll = (): void => {
    const startYear = now.getFullYear() - 1;
    recalculateMutation.mutate({
      from_year: startYear,
      from_month: now.getMonth() + 1,
      to_year: now.getFullYear(),
      to_month: now.getMonth() + 1,
    });
  };

  const handleCalculateMonth = (): void => {
    calculateMutation.mutate({
      from_year: selectedPeriod.year,
      from_month: selectedPeriod.month,
      to_year: selectedPeriod.year,
      to_month: selectedPeriod.month,
    });
  };

  const isCalculating = calculateMutation.isPending || recalculateMutation.isPending;
  const hasData = globalMetrics != null && globalMetrics.project_count > 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Global Metrics</h1>
          <p className="text-muted-foreground mt-1">
            {formatPeriodLabel(selectedPeriod.year, selectedPeriod.month)}
            {hasData && ` • ${globalMetrics!.project_count} project${globalMetrics!.project_count !== 1 ? 's' : ''}`}
          </p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleCalculateAll}
              disabled={isCalculating}
            >
              <Calculator className="w-4 h-4 mr-2" />
              {calculateMutation.isPending ? 'Calculating...' : 'Calculate All'}
            </Button>
            <Button
              variant="outline"
              onClick={handleRecalculateAll}
              disabled={isCalculating}
            >
              <RefreshCw className={cn('w-4 h-4 mr-2', recalculateMutation.isPending && 'animate-spin')} />
              Recalculate
            </Button>
          </div>
        )}
      </div>

      {/* Export */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <FileDown className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">From</span>
            <MonthYearPicker
              month={exportFromMonth}
              year={exportFromYear}
              onMonthChange={setExportFromMonth}
              onYearChange={setExportFromYear}
              disabled={isExporting}
            />
            <span className="text-sm text-muted-foreground">to</span>
            <MonthYearPicker
              month={exportToMonth}
              year={exportToYear}
              onMonthChange={setExportToMonth}
              onYearChange={setExportToYear}
              disabled={isExporting}
            />
            <NativeSelect
              value={exportSnapshotType}
              onChange={(e) => setExportSnapshotType(e.target.value)}
              disabled={isExporting}
            >
              <option value="cumulative">Cumulative</option>
              <option value="punctual">Punctual</option>
            </NativeSelect>
            <Button
              variant="outline"
              onClick={handleExport}
              disabled={isExporting}
            >
              {isExporting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <FileDown className="mr-2 h-4 w-4" />
                  Export XLSX
                </>
              )}
            </Button>
            {exportError && (
              <span className="text-sm text-red-600">{exportError}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Timeline */}
      <Card>
        <CardContent className="pt-6">
          <GlobalTimelineChart
            periods={periods}
            history={history}
            selectedPeriod={selectedPeriod}
            onPeriodChange={setSelectedPeriod}
          />
        </CardContent>
      </Card>

      {!hasData ? (
        <Card>
          <CardContent className="pt-6 text-center py-12">
            <Globe className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground mb-4">
              No global metrics calculated for {formatPeriodLabel(selectedPeriod.year, selectedPeriod.month)}
            </p>
            {isAdmin && (
              <Button onClick={handleCalculateMonth} disabled={isCalculating}>
                <Calculator className="w-4 h-4 mr-2" />
                Calculate This Month
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Score Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlobalScoreCard
              metrics={globalMetrics!}
              thresholds={thresholds}
              history={history}
              visibleDimensions={visibleDimensions}
              onToggleDimension={handleToggleDimension}
            />
            <DimensionBreakdownChart
              metrics={globalMetrics!}
              history={history}
              visibleDimensions={visibleDimensions}
              onToggleDimension={handleToggleDimension}
            />
          </div>

          <Separator className="my-6" />

          {/* Metrics Grid - ordered by dimension like ProjectDetail */}
          <div>
            <h2 className="text-2xl font-semibold mb-4">All Metrics</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {/* === TIME === */}
              <GlobalMetricCard
                label="Schedule Performance (SPI)"
                dimension="Time"
                indicator={globalMetrics!.indicators.spi}
                kpis={[{ label: 'KPI', value: '1.0' }]}
                historicalData={getIndicatorHistory('spi')}
              />
              <GlobalMetricCard
                label="On-Time Milestones"
                dimension="Time"
                indicator={globalMetrics!.indicators.on_time_milestones}
                kpis={[{ label: 'KPI', value: '100%' }]}
                historicalData={getIndicatorHistory('on_time_milestones')}
              />

              {/* === COST === */}
              <GlobalMetricCard
                label="Cost Performance (CPI)"
                dimension="Cost"
                indicator={globalMetrics!.indicators.cpi}
                kpis={[{ label: 'KPI', value: '1.0' }]}
                historicalData={getIndicatorHistory('cpi')}
              />

              {/* === QUALITY === */}
              <GlobalMetricCard
                label="Defect Density"
                dimension="Quality"
                indicator={globalMetrics!.indicators.defect_density}
                format="number"
                invert
                kpis={[{ label: 'KPI', value: '< 3%' }]}
                historicalData={getIndicatorHistory('defect_density')}
              />
              <GlobalMetricCard
                label="Escaped Rate"
                dimension="Quality"
                indicator={globalMetrics!.indicators.escaped_rate}
                format="number"
                invert
                kpis={[{ label: 'KPI', value: '< 1%' }]}
                historicalData={getIndicatorHistory('escaped_rate')}
              />
              <GlobalMetricCard
                label="MTTR"
                dimension="Quality"
                indicator={globalMetrics!.indicators.mttr_hours}
                format="hours"
                invert
                kpis={[{ label: 'KPI', value: '< 48h' }]}
                historicalData={getIndicatorHistory('mttr_hours')}
              />
              <GlobalMetricCard
                label="Story Review Ratio"
                dimension="Quality"
                indicator={globalMetrics!.indicators.story_review_ratio}
                kpis={[{ label: 'KPI', value: '> 90%' }]}
                historicalData={getIndicatorHistory('story_review_ratio')}
              />
              <GlobalMetricCard
                label="Test Maturity"
                dimension="Quality"
                indicator={globalMetrics!.indicators.test_maturity}
                kpis={[{ label: 'KPI', value: '> 80%' }]}
                historicalData={getIndicatorHistory('test_maturity')}
              />
              <GlobalMetricCard
                label="Security Vulnerabilities"
                dimension="Quality"
                indicator={globalMetrics!.indicators.high_vulns}
                format="number"
                invert
                kpis={[{ label: 'KPI', value: '0' }]}
                historicalData={getIndicatorHistory('high_vulns')}
              />

              {/* === VALUE === */}
              <GlobalMetricCard
                label="Strategic Impact"
                dimension="Value"
                indicator={globalMetrics!.indicators.strategic_impact}
                historicalData={getIndicatorHistory('strategic_impact')}
              />

              {/* === SATISFACTION === */}
              <GlobalMetricCard
                label="Client Satisfaction (PM Est.)"
                dimension="Satisfaction"
                indicator={globalMetrics!.indicators.pm_satisfaction}
                kpis={[{ label: 'KPI', value: '> 80%' }]}
                historicalData={getIndicatorHistory('pm_satisfaction')}
              />
              <GlobalMetricCard
                label="Client Satisfaction Survey"
                dimension="Satisfaction"
                indicator={globalMetrics!.indicators.client_satisfaction}
                kpis={[{ label: 'KPI', value: '> 80%' }]}
                historicalData={getIndicatorHistory('client_satisfaction')}
              />

              {/* === FLOW === */}
              <GlobalMetricCard
                label="Lead Time"
                dimension="Flow"
                indicator={globalMetrics!.indicators.lead_time_days}
                format="days"
                invert
                kpis={[{ label: 'KPI', value: '< 5d' }]}
                historicalData={getIndicatorHistory('lead_time_days')}
              />
              <GlobalMetricCard
                label="Commitment Reliability"
                dimension="Flow"
                indicator={globalMetrics!.indicators.commitment_reliability}
                kpis={[{ label: 'KPI', value: '> 85%' }]}
                historicalData={getIndicatorHistory('commitment_reliability')}
              />
              <GlobalMetricCard
                label="Deployment Frequency"
                dimension="Flow"
                indicator={globalMetrics!.indicators.deployment_frequency}
                format="number"
                kpis={[{ label: 'KPI', value: '≥ 1/day' }]}
                historicalData={getIndicatorHistory('deployment_frequency')}
              />
              <GlobalMetricCard
                label="Change Failure Rate"
                dimension="Flow"
                indicator={globalMetrics!.indicators.change_failure_rate}
                format="percent"
                invert
                kpis={[{ label: 'KPI', value: '< 15%' }]}
                historicalData={getIndicatorHistory('change_failure_rate')}
              />

              {/* === ENGINEERING === */}
              <GlobalMetricCard
                label="Architecture Checklist"
                dimension="Engineering"
                indicator={globalMetrics!.indicators.arch_checklist}
                kpis={[{ label: 'KPI', value: '100%' }]}
                historicalData={getIndicatorHistory('arch_checklist')}
              />
              <GlobalMetricCard
                label="PR Review Coverage"
                dimension="Engineering"
                indicator={globalMetrics!.indicators.pr_review_ratio}
                kpis={[{ label: 'KPI', value: '> 95%' }]}
                historicalData={getIndicatorHistory('pr_review_ratio')}
              />

              {/* === RISK === */}
              <GlobalMetricCard
                label="Governance Compliance"
                dimension="Risk"
                indicator={globalMetrics!.indicators.governance_compliance}
                kpis={[{ label: 'KPI', value: '100%' }]}
                historicalData={getIndicatorHistory('governance_compliance')}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
