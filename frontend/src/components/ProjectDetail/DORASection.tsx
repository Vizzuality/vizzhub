import { Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import SubIndicatorCard, { type HistoricalDataPoint } from '../SubIndicatorCard';
import type { FinalScore, Metrics, Indicators, MetricsWithScores } from '../../types';

type IndicatorKey = keyof Indicators;

function formatPeriod(year: number, month: number): string {
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[month - 1]} ${year.toString().slice(-2)}`;
}

function getHistoricalData(
  snapshots: MetricsWithScores[] | undefined,
  indicatorKey: IndicatorKey,
  multiplier = 1,
): HistoricalDataPoint[] {
  if (!snapshots || snapshots.length === 0) return [];
  return snapshots
    .slice()
    .reverse()
    .map((s) => ({
      period: formatPeriod(s.period_year, s.period_month),
      value: s.indicators[indicatorKey] !== null && s.indicators[indicatorKey] !== undefined
        ? (s.indicators[indicatorKey] as number) * multiplier
        : null,
    }));
}

interface DORASectionProps {
  scores: FinalScore;
  metrics: Metrics;
  indicators: Indicators;
  getTarget: (name: string) => number | null;
  snapshots?: MetricsWithScores[];
}

export default function DORASection({
  scores,
  metrics,
  indicators,
  getTarget,
  snapshots,
}: DORASectionProps): JSX.Element | null {
  if (!scores.dora || scores.dora.score === null) return null;

  return (
    <>
      <Separator className="my-6" />
      <div>
        <h2 className="text-2xl font-semibold mb-4">DORA Score</h2>
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-lg">Performance</CardTitle>
                <p className="text-sm text-muted-foreground">DevOps Research and Assessment</p>
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground transition-colors">
                      <Info className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="text-sm">
                      <strong>DORA metrics</strong> measure software delivery performance. They
                      track Deployment Frequency, Lead Time, Change Failure Rate, and MTTR.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="text-5xl font-bold">{scores.dora.score}</div>
                <div>
                  <span
                    className={cn(
                      'inline-block px-3 py-1 rounded-full text-sm font-medium',
                      scores.dora.classification === 'Elite' &&
                        'bg-score-green/20 text-score-green',
                      scores.dora.classification === 'High' && 'bg-accent/20 text-accent',
                      scores.dora.classification === 'Medium' &&
                        'bg-score-yellow/20 text-score-yellow',
                      scores.dora.classification === 'Low' && 'bg-score-red/20 text-score-red'
                    )}
                  >
                    {scores.dora.classification}
                  </span>
                  <p className="text-sm text-muted-foreground mt-1">
                    {scores.dora.available_metrics} of 4 metrics available
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* DORA Sub-indicators */}
        {metrics.github_metrics && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            {metrics.github_metrics.release_count_90d !== null &&
              metrics.github_metrics.release_count_90d !== undefined && (
                <SubIndicatorCard
                  title="Deployment Frequency"
                  indicatorValue={metrics.github_metrics.release_count_90d}
                  indicatorLabel="Releases in 90 days"
                  indicatorSuffix=" releases"
                  description="DORA metric: How often deployments occur"
                  target={(getTarget('target_deployment_frequency') ?? 1) * 90}
                  lowerIsBetter={false}
                  formula="count(releases in 90d)"
                  metrics={[
                    {
                      label: 'Per Day',
                      value:
                        metrics.github_metrics.deployment_frequency != null
                          ? parseFloat(metrics.github_metrics.deployment_frequency.toFixed(2))
                          : null,
                    },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'deployment_frequency')}
                />
              )}
            {indicators.lead_time_days !== null && (
                <SubIndicatorCard
                  title="Lead Time"
                  indicatorValue={indicators.lead_time_days}
                  indicatorLabel="Days from creation to completion"
                  indicatorSuffix=" days"
                  description="DORA metric: Time from issue creation to completion"
                  target={getTarget('target_lead_time_days')}
                  lowerIsBetter={true}
                  formula="avg(completed_at - created_at)"
                  metrics={[
                    { label: 'Sample Size', value: metrics.flow_metrics?.lead_time_sample_size ?? null },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'lead_time_days')}
                />
              )}
            {metrics.github_metrics.change_failure_rate !== null &&
              metrics.github_metrics.change_failure_rate !== undefined && (
                <SubIndicatorCard
                  title="Change Failure Rate"
                  indicatorValue={metrics.github_metrics.change_failure_rate}
                  indicatorLabel="Failure rate"
                  indicatorSuffix="%"
                  description="DORA metric: Releases requiring hotfix"
                  target={getTarget('target_change_failure_rate')}
                  lowerIsBetter={true}
                  formula="(failed / total) × 100"
                  metrics={[
                    { label: 'Total Releases', value: metrics.github_metrics.total_releases ?? null },
                    { label: 'Failed Releases', value: metrics.github_metrics.failed_releases ?? null },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'change_failure_rate')}
                />
              )}
            {indicators.mttr_hours !== null && (
              <SubIndicatorCard
                title="MTTR"
                indicatorValue={indicators.mttr_hours}
                indicatorLabel="Mean Time to Recovery"
                indicatorSuffix="h"
                description="DORA metric: Time to restore service after incident"
                target={getTarget('target_mttr_hours')}
                lowerIsBetter={true}
                formula="avg(resolved_at - created_at)"
                metrics={[
                  { label: 'Incidents', value: metrics.jira_defects?.incidents_count ?? 0 },
                ]}
                historicalData={getHistoricalData(snapshots, 'mttr_hours')}
              />
            )}
          </div>
        )}
      </div>
    </>
  );
}
