import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
import { ScorecardTable } from '../ScorecardTable';
import type { GlobalMetricsRecord, ScoringConfig } from '@/modules/scorecard/types';
import type { MonthColumn } from '../types';

vi.mock('../../../../hooks/useRegistryRows', () => ({
  useCreateRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateRegistryRow: () => ({ mutate: vi.fn() }),
  useDeleteRegistryRow: () => ({ mutate: vi.fn() }),
}));

function makeIndicatorValue(value: number): { value: number; count: number } {
  return { value, count: 5 };
}

function makeScoreValue(value: number): { value: number; count: number } {
  return { value, count: 5 };
}

const mockRecord: GlobalMetricsRecord = {
  id: 'test-id',
  period_year: 2025,
  period_month: 3,
  project_count: 5,
  created_at: '2025-03-01T00:00:00Z',
  updated_at: '2025-03-01T00:00:00Z',
  indicators: {
    spi: makeIndicatorValue(0.92),
    cpi: makeIndicatorValue(0.88),
    on_time_milestones: makeIndicatorValue(0.75),
    defect_density: makeIndicatorValue(0.85),
    escaped_rate: makeIndicatorValue(0.90),
    mttr_hours: makeIndicatorValue(0.70),
    governance_compliance: makeIndicatorValue(0.95),
    lead_time_days: makeIndicatorValue(0.65),
    deployment_frequency: makeIndicatorValue(0.80),
    change_failure_rate: makeIndicatorValue(0.88),
    commitment_reliability: makeIndicatorValue(0.72),
    pr_review_ratio: makeIndicatorValue(0.91),
    test_maturity: makeIndicatorValue(0.68),
    arch_checklist: makeIndicatorValue(0.82),
    high_vulns: makeIndicatorValue(0.95),
    okr_impact: makeIndicatorValue(0.80),
    pm_satisfaction: makeIndicatorValue(0.85),
    client_satisfaction: makeIndicatorValue(0.78),
    story_review_ratio: makeIndicatorValue(0.88),
    strategic_impact: makeIndicatorValue(0.75),
  },
  scores: {
    score: makeScoreValue(78.5),
    p_time: makeScoreValue(82.0),
    p_cost: makeScoreValue(74.3),
    p_quality: makeScoreValue(80.1),
    p_value: makeScoreValue(70.0),
    p_satisfaction: makeScoreValue(76.4),
    p_flow: makeScoreValue(65.2),
    p_engineering: makeScoreValue(88.0),
    p_risk: makeScoreValue(91.0),
  },
};

const mockMonths: MonthColumn[] = [
  { year: 2025, month: 3, label: 'Mar 2025' },
];

const mockGlobalWeights: ScoringConfig['global_weights'] = {
  time: 0.12,
  cost: 0.10,
  quality: 0.20,
  value: 0.05,
  satisfaction: 0.12,
  flow: 0.15,
  engineering: 0.20,
  risk: 0.05,
};

const mockTargets: ScoringConfig['targets'] = {
  defect_density: 5,
  escaped_rate: 2,
  mttr_hours: 24,
  spi: 0.85,
  cpi: 0.85,
  lead_time_days: 10,
  high_vuln_count: 0,
  gov_exceptions: 0,
  pr_no_review_ratio: 0.05,
  story_review_ratio: 0.8,
  client_satisfaction: 0.75,
  architecture: 0.8,
  commitment_reliability: 0.8,
  milestones_on_time: 0.8,
  test_maturity: 0.7,
  pm_satisfaction: 0.75,
  pr_size_lines: 400,
  review_turnaround_hours: 24,
  deployment_frequency: 0.1,
  change_failure_rate: 0.15,
  post_contract_tasks: 0,
  cost_variance: 0.1,
  governance_compliance: 0.9,
  okr_impact: 0.55,
};

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderTable(): void {
  const metricsByPeriod = new Map<string, GlobalMetricsRecord>();
  metricsByPeriod.set('2025-3', mockRecord);

  render(
    <QueryClientProvider client={queryClient}>
      <ScorecardTable
        months={mockMonths}
        metricsByPeriod={metricsByPeriod}
        globalWeights={mockGlobalWeights}
        targets={mockTargets}
        manualRows={[]}
        nodeId="test-node"
        isEditor={false}
        selectedYear={2025}
      />
    </QueryClientProvider>,
  );
}

describe('ScorecardTable', () => {
  it('renders FINAL SCORE and dimension rows', () => {
    renderTable();

    expect(screen.getByText('FINAL SCORE')).toBeInTheDocument();
    expect(screen.getByText('P_time — Schedule')).toBeInTheDocument();
    expect(screen.getByText('P_cost — Budget')).toBeInTheDocument();
    expect(screen.getByText('P_quality — Quality')).toBeInTheDocument();
    expect(screen.getByText('P_value — Strategic Value')).toBeInTheDocument();
    expect(screen.getByText('P_satisfaction — Satisfaction')).toBeInTheDocument();
    expect(screen.getByText('P_flow — Flow & Predictability')).toBeInTheDocument();
    expect(screen.getByText('P_engineering — Engineering Maturity')).toBeInTheDocument();
    expect(screen.getByText('P_risk — Risk Posture')).toBeInTheDocument();
  });

  it('shows score values in monthly columns', () => {
    renderTable();

    // FINAL SCORE value: 78.5
    expect(screen.getByText('78.5')).toBeInTheDocument();
    // p_time score: 82.0
    expect(screen.getByText('82')).toBeInTheDocument();
    // spi indicator: 0.92 -> rounded to 1 decimal = 0.9 (multiple indicators may share this value)
    expect(screen.getAllByText('0.9').length).toBeGreaterThan(0);
  });

  it('collapses and expands dimensions', async () => {
    const user = userEvent.setup();
    renderTable();

    // SPI row should be visible initially
    expect(screen.getByText('Schedule Performance Index')).toBeInTheDocument();

    // Click the P_time dimension to collapse it
    const pTimeRow = screen.getByText('P_time — Schedule').closest('tr');
    await user.click(pTimeRow!);

    // SPI row should now be hidden
    expect(screen.queryByText('Schedule Performance Index')).not.toBeInTheDocument();

    // Click P_time again to expand
    await user.click(pTimeRow!);

    // SPI row should be visible again
    expect(screen.getByText('Schedule Performance Index')).toBeInTheDocument();
  });
});
