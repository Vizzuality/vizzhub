import { Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import SubIndicatorCard from '../SubIndicatorCard';
import GovernanceCard from './GovernanceCard';
import PMSatisfactionCard from './PMSatisfactionCard';
import StrategicImpactCard from './StrategicImpactCard';
import TestMaturityCard from './TestMaturityCard';
import ArchitectureCard from './ArchitectureCard';
import ClientSurveyCard from './ClientSurveyCard';
import { formatDate } from '../../utils/formatters';
import { getHistoricalData } from '../../utils/chartUtils';
import type { Metrics, Indicators, Project, StrategicImpact, PMSatisfaction, TestMaturity, Architecture, MetricsWithScores, Dimension } from '../../types';

interface ConditionalCardProps {
  readonly hasData: boolean;
  readonly hasParentData: boolean;
  readonly card: JSX.Element;
  readonly mutedProps: { title: string; dimension: Dimension; description: string; message: string };
}

function renderConditionalCard({ hasData, hasParentData, card, mutedProps }: ConditionalCardProps): JSX.Element | null {
  if (hasData) return card;
  if (hasParentData) return <MutedCard {...mutedProps} />;
  return null;
}

const DIMENSION_COLORS: Record<Dimension, string> = {
  Time: 'text-chart-1',
  Cost: 'text-chart-2',
  Quality: 'text-chart-4',
  Value: 'text-chart-5',
  Satisfaction: 'text-chart-6',
  Flow: 'text-chart-3',
  Engineering: 'text-chart-7',
  Risk: 'text-chart-8',
};

const DIMENSION_ABBREV: Record<Dimension, string> = {
  Time: 'T',
  Cost: 'C',
  Quality: 'Q',
  Value: 'V',
  Satisfaction: 'S',
  Flow: 'F',
  Engineering: 'E',
  Risk: 'R',
};

function MutedCard({ title, dimension, description, message }: { title: string; dimension: Dimension; description: string; message: string }): JSX.Element {
  return (
    <Card className="opacity-60">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-xs font-semibold ${DIMENSION_COLORS[dimension]} shrink-0 cursor-help`}>
                    {DIMENSION_ABBREV[dimension]}
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">{dimension} metric</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {title}
          </span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-muted-foreground hover:text-foreground transition-colors">
                  <Info className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-sm">{description}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent>
        <div className="text-center py-4">
          <p className="text-2xl font-semibold text-muted-foreground">No data</p>
          <p className="text-xs text-muted-foreground mt-1">{message}</p>
        </div>
      </CardContent>
    </Card>
  );
}

type SurveyKey = 'understanding' | 'proactivity' | 'communication' | 'delivery_time' | 'response_time' | 'quality' | 'expectations' | 'recommend';

interface QualityMetricsGridProps {
  readonly metrics: Metrics;
  readonly indicators: Indicators;
  readonly project: Project;
  readonly getTarget: (name: string) => number | null;
  readonly getWeight: (category: string, name: string) => number | null;
  readonly onUpdateGovernance: (value: number) => Promise<unknown>;
  readonly onUpdatePMSatisfaction: (data: PMSatisfaction) => Promise<unknown>;
  readonly onUpdateStrategicImpact: (value: StrategicImpact) => Promise<unknown>;
  readonly onUpdateTestMaturity: (data: Partial<TestMaturity>) => Promise<unknown>;
  readonly onUpdateArchitecture: (data: Architecture) => Promise<unknown>;
  readonly onUpdateClientSurvey: (data: Partial<Record<SurveyKey, number>>) => Promise<unknown>;
  readonly isUpdatingGovernance: boolean;
  readonly isUpdatingPMSatisfaction: boolean;
  readonly isUpdatingStrategicImpact: boolean;
  readonly isUpdatingTestMaturity: boolean;
  readonly isUpdatingArchitecture: boolean;
  readonly isUpdatingClientSurvey: boolean;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
}

function isDimensionVisible(visibleDimensions: Set<Dimension> | undefined, dimension: Dimension): boolean {
  if (!visibleDimensions) return true;
  return visibleDimensions.has(dimension);
}

function hasAnyVisibleDimension(visibleDimensions: Set<Dimension> | undefined, dimensions: Dimension[]): boolean {
  return dimensions.some(d => isDimensionVisible(visibleDimensions, d));
}

export default function QualityMetricsGrid({
  metrics,
  indicators,
  project,
  getTarget,
  getWeight,
  onUpdateGovernance,
  onUpdatePMSatisfaction,
  onUpdateStrategicImpact,
  onUpdateTestMaturity,
  onUpdateArchitecture,
  onUpdateClientSurvey,
  isUpdatingGovernance,
  isUpdatingPMSatisfaction,
  isUpdatingStrategicImpact,
  isUpdatingTestMaturity,
  isUpdatingArchitecture,
  isUpdatingClientSurvey,
  snapshots,
  visibleDimensions,
}: QualityMetricsGridProps): JSX.Element | null {
  if (!metrics.jira_defects) return null;

  const relevantDimensions: Dimension[] = ['Quality', 'Value', 'Satisfaction', 'Flow', 'Engineering', 'Risk'];
  if (!hasAnyVisibleDimension(visibleDimensions, relevantDimensions)) return null;

  const showQuality = isDimensionVisible(visibleDimensions, 'Quality');
  const showValue = isDimensionVisible(visibleDimensions, 'Value');
  const showSatisfaction = isDimensionVisible(visibleDimensions, 'Satisfaction');
  const showFlow = isDimensionVisible(visibleDimensions, 'Flow');
  const showEngineering = isDimensionVisible(visibleDimensions, 'Engineering');
  const showRisk = isDimensionVisible(visibleDimensions, 'Risk');

  return (
    <>
      <Separator className="my-6" />
      <div>
        <h2 className="text-2xl font-semibold mb-4">Quality & Security Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* === QUALITY === */}
          {showQuality && (
            <>
              <SubIndicatorCard
                title="Defect Density"
                dimension="Quality"
                indicatorValue={indicators.defect_density}
                indicatorLabel="Bugs per 100 tasks"
                indicatorSuffix="%"
                description="Ratio of bugs to completed tasks"
                target={getTarget('target_defect_density')}
                lowerIsBetter={true}
                formula="(Bugs / Tasks) × 100"
                metrics={[
                  { label: 'Bugs', value: metrics.jira_defects.bugs_total },
                  { label: 'Tasks Completed', value: metrics.jira_defects.tasks_completed },
                ]}
                historicalData={getHistoricalData(snapshots, 'defect_density')}
              />
              <SubIndicatorCard
                title="Escaped Rate"
                dimension="Quality"
                indicatorValue={indicators.escaped_rate}
                indicatorLabel="Escaped per 100 tasks"
                indicatorSuffix="%"
                description="Bugs found in Staging/Production"
                target={getTarget('target_escaped_rate')}
                lowerIsBetter={true}
                formula="(Escaped / Tasks) × 100"
                metrics={[
                  { label: 'Escaped Defects', value: metrics.jira_defects.escaped_defects },
                  { label: 'Tasks Completed', value: metrics.jira_defects.tasks_completed },
                ]}
                historicalData={getHistoricalData(snapshots, 'escaped_rate')}
              />
              <SubIndicatorCard
                title="MTTR"
                dimension="Quality"
                indicatorValue={indicators.mttr_hours}
                indicatorLabel="Business hours"
                indicatorSuffix="h"
                description="Mean Time To Repair"
                target={getTarget('target_mttr_hours')}
                lowerIsBetter={true}
                formula="avg(resolved - created)"
                metrics={[{ label: 'Incidents', value: metrics.jira_defects.incidents_count }]}
                historicalData={getHistoricalData(snapshots, 'mttr_hours')}
              />
              {metrics.flow_metrics ? (
                <SubIndicatorCard
                  title="Story Review Ratio"
                  dimension="Quality"
                  indicatorValue={
                    indicators.story_review_ratio !== null
                      ? indicators.story_review_ratio * 100
                      : null
                  }
                  indicatorLabel="Stories with reviewer"
                  indicatorSuffix="%"
                  description="User stories with assigned reviewer"
                  target={getTarget('target_story_review_ratio')}
                  lowerIsBetter={false}
                  formula="(with_reviewer / total) × 100"
                  metrics={[
                    { label: 'With Reviewer', value: metrics.flow_metrics.stories_with_reviewer },
                    { label: 'Total Stories', value: metrics.flow_metrics.total_stories },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'story_review_ratio', 100)}
                />
              ) : (
                <MutedCard title="Story Review Ratio" dimension="Quality" description="User stories with assigned reviewer" message="No flow metrics available" />
              )}
              <TestMaturityCard
                data={metrics.test_maturity}
                indicatorValue={indicators.test_maturity}
                target={getTarget('target_test_maturity')}
                onSave={onUpdateTestMaturity}
                isPending={isUpdatingTestMaturity}
                historicalData={getHistoricalData(snapshots, 'test_maturity')}
              />
              {metrics.github_metrics ? (
                <SubIndicatorCard
                  title="Security Vulnerabilities"
                  dimension="Quality"
                  indicatorValue={metrics.github_metrics.high_severity_vulns}
                  indicatorLabel="High/Critical open >30d"
                  indicatorSuffix=""
                  description="Dependabot alerts unaddressed for 30+ days"
                  target={getTarget('target_high_vuln_count')}
                  lowerIsBetter={true}
                  formula="count(high/critical vulns >30d)"
                  metrics={[
                    { label: 'Total Open', value: metrics.github_metrics.high_severity_vulns_total ?? 0 },
                    { label: 'Older than 30d', value: metrics.github_metrics.high_severity_vulns },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'high_vulns')}
                />
              ) : (
                <MutedCard title="Security Vulnerabilities" dimension="Quality" description="Dependabot alerts unaddressed for 30+ days" message="No GitHub data available" />
              )}
            </>
          )}

          {/* === VALUE === */}
          {showValue && (
            <StrategicImpactCard
              value={metrics.strategic_impact}
              onSave={onUpdateStrategicImpact}
              isPending={isUpdatingStrategicImpact}
            />
          )}

          {/* === SATISFACTION === */}
          {showSatisfaction && (
            <>
              <PMSatisfactionCard
                data={metrics.pm_satisfaction}
                indicatorValue={indicators.pm_satisfaction}
                target={getTarget('target_pm_satisfaction')}
                onSave={onUpdatePMSatisfaction}
                isPending={isUpdatingPMSatisfaction}
                historicalData={getHistoricalData(snapshots, 'pm_satisfaction')}
              />
              <ClientSurveyCard
                data={metrics.client_survey}
                indicatorValue={indicators.client_satisfaction}
                target={getTarget('target_client_satisfaction')}
                projectStatus={project.status}
                onSave={onUpdateClientSurvey}
                isPending={isUpdatingClientSurvey}
                getWeight={(name) => getWeight('Client Survey Weights', name)}
              />
            </>
          )}

          {/* === FLOW === */}
          {showFlow && (
            <>
              <SubIndicatorCard
                title="Lead Time"
                dimension="Flow"
                indicatorValue={indicators.lead_time_days}
                indicatorLabel="Business days"
                indicatorSuffix="d"
                description="In Progress → Done"
                target={getTarget('target_lead_time_days')}
                lowerIsBetter={true}
                formula="avg(done - in_progress)"
                metrics={[
                  { label: 'Issues', value: metrics.flow_metrics?.lead_time_sample_size ?? null },
                ]}
                historicalData={getHistoricalData(snapshots, 'lead_time_days')}
              />
              <SubIndicatorCard
                title="Commitment Reliability"
                dimension="Flow"
                indicatorValue={
                  indicators.commitment_reliability !== null
                    ? indicators.commitment_reliability * 100
                    : null
                }
                indicatorLabel="Single-sprint ratio"
                indicatorSuffix="%"
                description="Issues completed in original sprint"
                target={getTarget('target_commitment_reliability')}
                lowerIsBetter={false}
                formula="single_sprint / committed"
                metrics={[
                  { label: 'Committed', value: metrics.flow_metrics?.committed_issues ?? null },
                  { label: 'Single Sprint', value: metrics.flow_metrics?.single_sprint_issues ?? null },
                ]}
                historicalData={getHistoricalData(snapshots, 'commitment_reliability', 100)}
              />
            </>
          )}

          {/* === ENGINEERING === */}
          {showEngineering && (
            <>
              <ArchitectureCard
                data={metrics.architecture}
                indicatorValue={indicators.arch_checklist}
                target={getTarget('target_architecture')}
                onSave={onUpdateArchitecture}
                isPending={isUpdatingArchitecture}
                historicalData={getHistoricalData(snapshots, 'arch_checklist')}
              />
              {metrics.github_metrics ? (
                <SubIndicatorCard
                  title="PR Review Coverage"
                  dimension="Engineering"
                  indicatorValue={
                    metrics.github_metrics.pr_review_ratio !== null &&
                    metrics.github_metrics.pr_review_ratio !== undefined
                      ? metrics.github_metrics.pr_review_ratio * 100
                      : null
                  }
                  indicatorLabel="Review coverage"
                  indicatorSuffix="%"
                  description="PRs reviewed before merge"
                  target={getTarget('target_pr_no_review_ratio') !== null ? 100 - getTarget('target_pr_no_review_ratio')! : null}
                  lowerIsBetter={false}
                  formula="(reviewed / total) × 100"
                  metrics={[
                    {
                      label: 'Reviewed',
                      value:
                        metrics.github_metrics.total_merged_prs -
                        metrics.github_metrics.prs_without_review,
                    },
                    { label: 'Total Merged', value: metrics.github_metrics.total_merged_prs },
                  ]}
                  historicalData={getHistoricalData(snapshots, 'pr_review_ratio', 100)}
                />
              ) : (
                <MutedCard title="PR Review Coverage" dimension="Engineering" description="PRs reviewed before merge" message="No GitHub data available" />
              )}
              {renderConditionalCard({
                hasData: metrics.github_metrics?.pr_size_median != null,
                hasParentData: !!metrics.github_metrics,
                card: (
                  <SubIndicatorCard
                    title="PR Size"
                    dimension="Engineering"
                    indicatorValue={metrics.github_metrics?.pr_size_median ?? null}
                    indicatorLabel="Median lines changed"
                    indicatorSuffix=" lines"
                    description="Median PR size (additions + deletions)"
                    target={getTarget('target_pr_size_lines')}
                    lowerIsBetter={true}
                    formula="median(additions + deletions)"
                    metrics={[
                      { label: 'Total Merged PRs', value: metrics.github_metrics?.total_merged_prs ?? 0 },
                    ]}
                    historicalData={getHistoricalData(snapshots, 'pr_size_median')}
                  />
                ),
                mutedProps: { title: 'PR Size', dimension: 'Engineering', description: 'Median PR size (additions + deletions)', message: 'No PR size data available' },
              })}
              {renderConditionalCard({
                hasData: metrics.github_metrics?.review_turnaround_hours != null,
                hasParentData: !!metrics.github_metrics,
                card: (
                  <SubIndicatorCard
                    title="Review Turnaround"
                    dimension="Engineering"
                    indicatorValue={metrics.github_metrics?.review_turnaround_hours ?? null}
                    indicatorLabel="Median hours to first review"
                    indicatorSuffix="h"
                    description="Time from PR creation to first review"
                    target={getTarget('target_review_turnaround_hours')}
                    lowerIsBetter={true}
                    formula="median(first_review - pr_created)"
                    metrics={[
                      { label: 'Total Merged PRs', value: metrics.github_metrics?.total_merged_prs ?? 0 },
                    ]}
                    historicalData={getHistoricalData(snapshots, 'review_turnaround_hours')}
                  />
                ),
                mutedProps: { title: 'Review Turnaround', dimension: 'Engineering', description: 'Time from PR creation to first review', message: 'No review turnaround data available' },
              })}
            </>
          )}

          {/* === RISK === */}
          {showRisk && (
            <>
              <GovernanceCard
                value={metrics.governance_exceptions}
                target={getTarget('target_gov_exceptions')}
                onSave={onUpdateGovernance}
                isPending={isUpdatingGovernance}
                historicalData={getHistoricalData(snapshots, 'governance_compliance')}
              />
              {indicators.post_contract_tasks === null ? (
                <MutedCard title="Post-Contract Tasks" dimension="Risk" description="New tasks created >30 days after contract end" message="No post-contract data available" />
              ) : (
                <SubIndicatorCard
                  title="Post-Contract Tasks"
                  dimension="Risk"
                  indicatorValue={indicators.post_contract_tasks}
                  indicatorLabel="Tasks after closure"
                  indicatorSuffix=""
                  description="New tasks created >30 days after contract end"
                  target={getTarget('target_post_contract_tasks')}
                  lowerIsBetter={true}
                  formula="count(tasks created after end_date + 30d)"
                  historicalData={getHistoricalData(snapshots, 'post_contract_tasks')}
                  metrics={[
                    {
                      label: 'Contract End',
                      value: project.end_date ? formatDate(project.end_date) : 'Not set',
                    },
                  ]}
                />
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
