import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import QualityMetricsGrid from '../QualityMetricsGrid';
import type { Metrics, Indicators } from '../../../types';
import type { Project } from '@/core/types/project';

const noop = async (): Promise<void> => {};

const baseIndicators: Indicators = {
  spi: null,
  on_time_milestones: null,
  cpi: null,
  cost_variance_pct: null,
  defect_density: null,
  escaped_rate: null,
  mttr_hours: null,
  governance_compliance: null,
  lead_time_days: null,
  commitment_reliability: null,
  pr_review_ratio: null,
  prs_without_review: null,
  high_vulns: null,
  test_maturity: null,
  arch_checklist: null,
  story_review_ratio: null,
  okr_impact: null,
  pm_satisfaction: null,
  client_satisfaction: null,
  pr_size_median: null,
  review_turnaround_hours: null,
  deployment_frequency: null,
  change_failure_rate: null,
  post_contract_tasks: null,
};

function makeMetrics(highVulns: number | null): Metrics {
  return {
    jira_defects: { bugs_total: 0, tasks_completed: 10, escaped_defects: 0, incidents_count: 0 },
    github_metrics: {
      prs_without_review: 0,
      total_merged_prs: 5,
      high_severity_vulns: highVulns,
      high_severity_vulns_total: highVulns,
    },
  } as unknown as Metrics;
}

function makeProject(hasDependabotAlerts: boolean): Project {
  return { id: 'p1', has_dependabot_alerts: hasDependabotAlerts, status: 'active' } as unknown as Project;
}

function renderGrid(highVulns: number | null, hasAlerts: boolean) {
  return render(
    <MemoryRouter>
      <QualityMetricsGrid
        metrics={makeMetrics(highVulns)}
        indicators={baseIndicators}
        project={makeProject(hasAlerts)}
        getTarget={() => null}
        getWeight={() => null}
        onUpdateGovernance={noop}
        onUpdatePMSatisfaction={noop}
        onUpdateStrategicImpact={noop}
        onUpdateTestMaturity={noop}
        onUpdateArchitecture={noop}
        onUpdateClientSurvey={noop}
        isUpdatingGovernance={false}
        isUpdatingPMSatisfaction={false}
        isUpdatingStrategicImpact={false}
        isUpdatingTestMaturity={false}
        isUpdatingArchitecture={false}
        isUpdatingClientSurvey={false}
        editable={false}
      />
    </MemoryRouter>,
  );
}

describe('Security Vulnerabilities — no-access badge', () => {
  it('shows the No access badge when vulns are null (Dependabot inaccessible)', () => {
    renderGrid(null, true);
    expect(screen.getByTestId('vulns-no-access-badge')).toBeInTheDocument();
    expect(screen.getByText('No access')).toBeInTheDocument();
  });

  it('does NOT show the No access badge when vulns are 0 (real clean repo)', () => {
    renderGrid(0, true);
    expect(screen.queryByTestId('vulns-no-access-badge')).not.toBeInTheDocument();
  });

  it('prefers the No access badge over Alerts off when both apply', () => {
    renderGrid(null, false);
    expect(screen.getByTestId('vulns-no-access-badge')).toBeInTheDocument();
    expect(screen.queryByTestId('alerts-off-badge')).not.toBeInTheDocument();
  });
});
