import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import EVMSection from '../EVMSection';
import type { EVMData, Indicators } from '../../../types';

const evmData: EVMData = {
  budget_total: 100000,
  cost_to_date: 50000,
  percent_completed: 0.4,
  percent_planned: 0.5,
};

const indicators: Indicators = {
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

const getTarget = (): number | null => null;

describe('CPI card — alerts-off badge', () => {
  it('renders Alerts off badge when budgetAlertsEnabled is false', () => {
    render(
      <MemoryRouter>
        <EVMSection
          projectId="p1"
          evmData={evmData}
          milestones={[]}
          indicators={indicators}
          getTarget={getTarget}
          budgetAlertsEnabled={false}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('alerts-off-badge')).toBeInTheDocument();
    expect(screen.getByText('Alerts off')).toBeInTheDocument();
  });

  it('does not render Alerts off badge when budgetAlertsEnabled is true', () => {
    render(
      <MemoryRouter>
        <EVMSection
          projectId="p1"
          evmData={evmData}
          milestones={[]}
          indicators={indicators}
          getTarget={getTarget}
          budgetAlertsEnabled={true}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId('alerts-off-badge')).not.toBeInTheDocument();
  });

  it('does not render Alerts off badge by default (prop omitted)', () => {
    render(
      <MemoryRouter>
        <EVMSection
          projectId="p1"
          evmData={evmData}
          milestones={[]}
          indicators={indicators}
          getTarget={getTarget}
        />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId('alerts-off-badge')).not.toBeInTheDocument();
  });
});
