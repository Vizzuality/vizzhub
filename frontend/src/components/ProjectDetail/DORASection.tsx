import { Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import SubIndicatorCard, { type HistoricalDataPoint } from '../SubIndicatorCard';
import type { DoraLevel, FinalScore, Metrics, Indicators, MetricsWithScores, Dimension } from '../../types';

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

function LevelBadge({ level }: { level: DoraLevel }): JSX.Element {
  return (
    <span
      className={cn(
        'inline-block px-2 py-0.5 rounded text-xs font-medium',
        level === 'Elite' && 'bg-score-green/20 text-score-green',
        level === 'High' && 'bg-accent/20 text-accent',
        level === 'Medium' && 'bg-score-yellow/20 text-score-yellow',
        level === 'Low' && 'bg-score-red/20 text-score-red'
      )}
    >
      {level}
    </span>
  );
}

interface DORASectionProps {
  scores: FinalScore;
  metrics: Metrics;
  indicators: Indicators;
  getTarget: (name: string) => number | null;
  snapshots?: MetricsWithScores[];
  visibleDimensions?: Set<Dimension>;
}

export default function DORASection({
  scores,
  metrics,
  indicators,
  getTarget,
  snapshots,
  visibleDimensions,
}: DORASectionProps): JSX.Element | null {
  const showFlow = !visibleDimensions || visibleDimensions.has('Flow');

  if (!scores.dora || scores.dora.score === null) return null;
  if (!showFlow) return null;

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
                  <TooltipContent className="max-w-md" side="left">
                    <div className="text-sm space-y-2">
                      <p>
                        <strong>DORA metrics</strong> measure software delivery performance using
                        official thresholds from the State of DevOps reports.
                      </p>
                      <div className="text-xs space-y-1 font-mono">
                        <p><strong>Deploy Freq:</strong> Elite ≥1/day, High ≥1/week, Med ≥1/month</p>
                        <p><strong>Lead Time:</strong> Elite &lt;1h, High &lt;1d, Med &lt;1w</p>
                        <p><strong>Failure Rate:</strong> Elite ≤5%, High ≤10%, Med ≤15%</p>
                        <p><strong>MTTR:</strong> Elite &lt;1h, High &lt;1d, Med &lt;1w</p>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Score = avg of level scores. Classification = weakest metric.
                      </p>
                    </div>
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
                  dimension="Flow"
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
                  badge={scores.dora?.metrics.deployment_frequency && (
                    <LevelBadge level={scores.dora.metrics.deployment_frequency.level} />
                  )}
                />
              )}
            {indicators.lead_time_days !== null && (
                <SubIndicatorCard
                  title="Lead Time"
                  dimension="Flow"
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
                  badge={scores.dora?.metrics.lead_time && (
                    <LevelBadge level={scores.dora.metrics.lead_time.level} />
                  )}
                />
              )}
            {metrics.github_metrics.change_failure_rate !== null &&
              metrics.github_metrics.change_failure_rate !== undefined && (
                <SubIndicatorCard
                  title="Change Failure Rate"
                  dimension="Flow"
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
                  badge={scores.dora?.metrics.change_failure_rate && (
                    <LevelBadge level={scores.dora.metrics.change_failure_rate.level} />
                  )}
                />
              )}
            {(metrics.jira_defects?.incidents_count ?? 0) > 0 ? (
              <SubIndicatorCard
                title="MTTR"
                dimension="Flow"
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
                badge={scores.dora?.metrics.mttr && (
                  <LevelBadge level={scores.dora.metrics.mttr.level} />
                )}
              />
            ) : (
              <Card className="opacity-60">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-xs font-semibold text-chart-3 shrink-0 cursor-help">
                              F
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-xs">Flow metric</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      MTTR
                      <LevelBadge level="Elite" />
                    </span>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button className="text-muted-foreground hover:text-foreground transition-colors">
                            <Info className="h-4 w-4" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-sm">Mean Time to Recovery - no incidents to measure</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">DORA metric: Time to restore service after incident</p>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-4">
                    <p className="text-2xl font-semibold text-muted-foreground">No incidents</p>
                    <p className="text-xs text-muted-foreground mt-1">No failures to recover from</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </>
  );
}
