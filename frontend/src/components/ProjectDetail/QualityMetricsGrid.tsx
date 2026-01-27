import { Separator } from '@/components/ui/separator';
import SubIndicatorCard from '../SubIndicatorCard';
import GovernanceCard from './GovernanceCard';
import PMSatisfactionCard from './PMSatisfactionCard';
import StrategicImpactCard from './StrategicImpactCard';
import TestMaturityCard from './TestMaturityCard';
import ArchitectureCard from './ArchitectureCard';
import ClientSurveyCard from './ClientSurveyCard';
import { formatDate } from '../../utils/formatters';
import type { Metrics, Indicators, Project, StrategicImpact, PMSatisfaction, TestMaturity, Architecture } from '../../types';

type SurveyKey = 'understanding' | 'proactivity' | 'communication' | 'delivery_time' | 'response_time' | 'quality' | 'expectations' | 'recommend';

interface QualityMetricsGridProps {
  metrics: Metrics;
  indicators: Indicators;
  project: Project;
  getTarget: (name: string) => number | null;
  getWeight: (category: string, name: string) => number | null;
  onUpdateGovernance: (value: number) => Promise<unknown>;
  onUpdatePMSatisfaction: (data: PMSatisfaction) => Promise<unknown>;
  onUpdateStrategicImpact: (value: StrategicImpact) => Promise<unknown>;
  onUpdateTestMaturity: (data: Partial<TestMaturity>) => Promise<unknown>;
  onUpdateArchitecture: (data: Architecture) => Promise<unknown>;
  onUpdateClientSurvey: (data: Partial<Record<SurveyKey, number>>) => Promise<unknown>;
  isUpdatingGovernance: boolean;
  isUpdatingPMSatisfaction: boolean;
  isUpdatingStrategicImpact: boolean;
  isUpdatingTestMaturity: boolean;
  isUpdatingArchitecture: boolean;
  isUpdatingClientSurvey: boolean;
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
}: QualityMetricsGridProps): JSX.Element | null {
  if (!metrics.jira_defects) return null;

  return (
    <>
      <Separator className="my-6" />
      <div>
        <h2 className="text-2xl font-semibold mb-4">Quality & Security Metrics</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <SubIndicatorCard
            title="Defect Density"
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
          />
          <SubIndicatorCard
            title="Escaped Rate"
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
          />
          <SubIndicatorCard
            title="MTTR"
            indicatorValue={indicators.mttr_hours}
            indicatorLabel="Business hours"
            indicatorSuffix="h"
            description="Mean Time To Repair"
            target={getTarget('target_mttr_hours')}
            lowerIsBetter={true}
            formula="avg(resolved - created)"
            metrics={[{ label: 'Incidents', value: metrics.jira_defects.incidents_count }]}
          />
          {metrics.flow_metrics && (
            <SubIndicatorCard
              title="Story Review Ratio"
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
            />
          )}
          <GovernanceCard
            value={metrics.governance_exceptions}
            target={getTarget('target_gov_exceptions')}
            onSave={onUpdateGovernance}
            isPending={isUpdatingGovernance}
          />
          <PMSatisfactionCard
            data={metrics.pm_satisfaction}
            indicatorValue={indicators.pm_satisfaction}
            target={getTarget('target_pm_satisfaction')}
            onSave={onUpdatePMSatisfaction}
            isPending={isUpdatingPMSatisfaction}
          />
          <StrategicImpactCard
            value={metrics.strategic_impact}
            onSave={onUpdateStrategicImpact}
            isPending={isUpdatingStrategicImpact}
          />
          <TestMaturityCard
            data={metrics.test_maturity}
            indicatorValue={indicators.test_maturity}
            target={getTarget('target_test_maturity')}
            onSave={onUpdateTestMaturity}
            isPending={isUpdatingTestMaturity}
          />
          <ArchitectureCard
            data={metrics.architecture}
            indicatorValue={indicators.arch_checklist}
            target={getTarget('target_architecture')}
            onSave={onUpdateArchitecture}
            isPending={isUpdatingArchitecture}
          />
          <SubIndicatorCard
            title="Lead Time"
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
          />
          <SubIndicatorCard
            title="Commitment Reliability"
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
          />
          {metrics.github_metrics && (
            <SubIndicatorCard
              title="PR Review Coverage"
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
            />
          )}
          {metrics.github_metrics &&
            metrics.github_metrics.pr_size_median !== null &&
            metrics.github_metrics.pr_size_median !== undefined && (
              <SubIndicatorCard
                title="PR Size"
                indicatorValue={metrics.github_metrics.pr_size_median}
                indicatorLabel="Median lines changed"
                indicatorSuffix=" lines"
                description="Median PR size (additions + deletions)"
                target={getTarget('target_pr_size_lines')}
                lowerIsBetter={true}
                formula="median(additions + deletions)"
                metrics={[
                  { label: 'Total Merged PRs', value: metrics.github_metrics.total_merged_prs },
                ]}
              />
            )}
          {metrics.github_metrics && (
            <SubIndicatorCard
              title="Security Vulnerabilities"
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
            />
          )}
          {indicators.post_contract_tasks !== null && (
            <SubIndicatorCard
              title="Post-Contract Tasks"
              indicatorValue={indicators.post_contract_tasks}
              indicatorLabel="Tasks after closure"
              indicatorSuffix=""
              description="New tasks created >30 days after contract end"
              target={getTarget('target_post_contract_tasks')}
              lowerIsBetter={true}
              formula="count(tasks created after end_date + 30d)"
              metrics={[
                {
                  label: 'Contract End',
                  value: project.end_date ? formatDate(project.end_date) : 'Not set',
                },
              ]}
            />
          )}
          <ClientSurveyCard
            data={metrics.client_survey}
            indicatorValue={indicators.client_satisfaction}
            target={getTarget('target_client_satisfaction')}
            projectStatus={project.status}
            onSave={onUpdateClientSurvey}
            isPending={isUpdatingClientSurvey}
            getWeight={(name) => getWeight('Client Survey Weights', name)}
          />
        </div>
      </div>
    </>
  );
}
