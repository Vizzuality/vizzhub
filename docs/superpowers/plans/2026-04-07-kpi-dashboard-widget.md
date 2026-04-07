# KPI Dashboard Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a KPI Dashboard widget for ISO Docs that combines live Global Scorecard data with manually-entered ISO KPIs, exportable to XLSX and Google Drive.

**Architecture:** Widget registered in `WIDGET_REGISTRY` with key `kpi_dashboard`. Scorecard section fetches live data from existing global metrics + config APIs (read-only). Manual KPIs section uses existing `RegistryRow` CRUD (editable). Export endpoint merges both into XLSX. No new DB models or migrations.

**Tech Stack:** React + TanStack Query (frontend), FastAPI + openpyxl (backend), existing `ExportService` and `export_helpers` for XLSX generation.

**Spec:** `docs/superpowers/specs/2026-04-07-kpi-dashboard-widget-design.md`

---

## File Map

### Frontend — Create

| File | Responsibility |
|------|---------------|
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/index.tsx` | Re-export + WIDGET_REGISTRY entry |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/KpiDashboard.tsx` | Main layout: toolbar (cycle selector, export) + 2 sections |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ScorecardTable.tsx` | Hierarchical collapsible table (read-only, live data) |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ManualKpiTable.tsx` | Editable table for manual KPIs |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/AddKpiDialog.tsx` | Dialog for adding new manual KPI |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/constants.ts` | Dimension/indicator definitions, ISO cycle helpers |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/types.ts` | Local interfaces |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/useKpiDashboard.ts` | Hook: combines global metrics + config + registry rows for a cycle |

### Frontend — Modify

| File | Change |
|------|--------|
| `frontend/src/modules/iso-docs/components/widgets/index.ts` | Import and register `KpiDashboard` |

### Backend — Create

| File | Responsibility |
|------|---------------|
| `backend/app/modules/iso_docs/api/widget_export.py` | `GET /widgets/{node_id}/export` endpoint |
| `backend/app/modules/iso_docs/services/kpi_export_service.py` | XLSX generation: scorecard sheet + manual KPIs sheet |

### Backend — Modify

| File | Change |
|------|--------|
| `backend/app/modules/iso_docs/router.py` | Mount widget export router |

### Tests — Create

| File | What it tests |
|------|--------------|
| `backend/tests/iso_docs/test_widget_export.py` | Export endpoint returns valid XLSX with correct structure |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/KpiDashboard.test.tsx` | Widget renders both sections with mock data |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx` | Hierarchical rendering, collapse/expand, traffic lights |
| `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx` | Add/edit/delete KPIs, inline editing |

---

## Task 1: Constants and Types

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/types.ts`
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/constants.ts`

- [ ] **Step 1: Create types.ts**

```typescript
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/types.ts
import type { RegistryRow } from '../../../types/registry';

export interface IsoCycle {
  year: number;       // e.g. 2025 means March 2025 – February 2026
  startYear: number;  // 2025
  startMonth: number; // 3
  endYear: number;    // 2026
  endMonth: number;   // 2
}

export interface ScorecardRowDef {
  key: string;
  name: string;
  description: string;
  formula: string;
  level: 0 | 1 | 2;
  parentKey?: string;
  weight?: string;
}

export interface MonthColumn {
  year: number;
  month: number;
  label: string; // "Mar 2025"
}

export type ManualKpiRow = RegistryRow;

export interface ManualKpiData {
  name: string;
  scope: string;
  responsible: string;
  methodology: string;
  formula: string;
  target: number | null;
  periodicity: string;
  [monthKey: string]: unknown; // m03, m04, ..., m02
}
```

- [ ] **Step 2: Create constants.ts**

Mirror the backend `export_definitions.py` hierarchy plus ISO cycle helpers.

```typescript
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/constants.ts
import type { IsoCycle, MonthColumn, ScorecardRowDef } from './types';

const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export const ISO_CYCLE_START_MONTH = 3; // March

export function getIsoCycle(year: number): IsoCycle {
  return {
    year,
    startYear: year,
    startMonth: 3,
    endYear: year + 1,
    endMonth: 2,
  };
}

export function getCycleMonths(cycle: IsoCycle): MonthColumn[] {
  const months: MonthColumn[] = [];
  let y = cycle.startYear;
  let m = cycle.startMonth;
  for (let i = 0; i < 12; i++) {
    months.push({
      year: y,
      month: m,
      label: `${SHORT_MONTHS[m - 1]} ${y}`,
    });
    m++;
    if (m > 12) {
      m = 1;
      y++;
    }
  }
  return months;
}

export function monthToDataKey(month: number): string {
  return `m${String(month).padStart(2, '0')}`;
}

export const INDICATOR_DEFINITIONS: Record<string, { name: string; description: string; formula: string }> = {
  spi: {
    name: 'Schedule Performance Index',
    description: 'Ratio of earned value to planned value. Measures schedule efficiency.',
    formula: 'EV / PV (where EV = budget_total * percent_completed, PV = budget_total * percent_planned)',
  },
  on_time_milestones: {
    name: 'On-Time Milestones',
    description: 'Weighted ratio of milestones delivered on time, with grace period.',
    formula: 'Sum(weight * on_time) / Sum(weight) for each milestone',
  },
  cpi: {
    name: 'Cost Performance Index',
    description: 'Ratio of earned value to actual cost. Measures cost efficiency.',
    formula: 'EV / AC (where EV = budget_total * percent_completed, AC = cost_to_date)',
  },
  budget_variance: {
    name: 'Budget Variance',
    description: 'Percentage of budget overrun.',
    formula: '(cost_to_date - planned_cost) / budget_total * 100',
  },
  defect_density: {
    name: 'Defect Density',
    description: 'Number of bugs per 100 completed tasks.',
    formula: '(bugs_total / tasks_completed) * 100',
  },
  escaped_rate: {
    name: 'Escaped Defect Rate',
    description: 'Escaped defects per 100 completed tasks.',
    formula: '(escaped_defects / tasks_completed) * 100',
  },
  mttr_hours: {
    name: 'Mean Time to Recovery',
    description: 'Average hours to resolve incidents.',
    formula: 'mttr_hours (from Jira resolution times)',
  },
  governance_compliance: {
    name: 'Governance Compliance',
    description: 'Compliance based on number of governance exceptions.',
    formula: 'max(0, 1 - (exceptions / target)). Zero exceptions = 1.0',
  },
  story_review_ratio: {
    name: 'Story Review Ratio',
    description: 'Ratio of stories that had a reviewer assigned.',
    formula: 'stories_with_reviewer / total_stories',
  },
  pr_review_ratio: {
    name: 'PR Review Ratio',
    description: 'Ratio of PRs merged with at least one review.',
    formula: '(total_merged_prs - prs_without_review) / total_merged_prs',
  },
  change_failure_rate: {
    name: 'Change Failure Rate',
    description: 'Percentage of releases that caused failures (DORA metric).',
    formula: 'failed_releases / total_releases * 100',
  },
  post_contract_tasks: {
    name: 'Post-Contract Tasks',
    description: 'Tasks created more than 30 days after contract end date.',
    formula: 'Count of tasks created > 30 days after project end_date',
  },
  okr_impact: {
    name: 'Strategic Impact',
    description: "Assessment of project's strategic value to the organization.",
    formula: 'LOW=0.25, MEDIUM=0.55, HIGH=0.80, TRANSFORMATIONAL=1.0',
  },
  pm_satisfaction: {
    name: 'PM Satisfaction',
    description: "Project manager's estimation of client satisfaction.",
    formula: 'Weighted score from delivery complaints, design complaints, overall estimation',
  },
  client_satisfaction: {
    name: 'Client Survey Score',
    description: 'Weighted average of 8 client survey questions (1-5 scale).',
    formula: 'Sum(question_score * question_weight) / Sum(question_weight), normalized to 0-1',
  },
  lead_time_days: {
    name: 'Lead Time',
    description: 'Average days from issue creation to completion.',
    formula: 'Average (done_date - created_date) for completed issues',
  },
  commitment_reliability: {
    name: 'Commitment Reliability',
    description: 'Ratio of issues completed within a single sprint.',
    formula: 'single_sprint_issues / committed_issues',
  },
  pr_size_median: {
    name: 'PR Size (Median)',
    description: 'Median number of changed lines per pull request.',
    formula: 'Median(additions + deletions) across merged PRs',
  },
  review_turnaround_hours: {
    name: 'Review Turnaround',
    description: 'Median hours from PR creation to first review.',
    formula: 'Median(first_review_time - pr_created_time) for reviewed PRs',
  },
  deployment_frequency: {
    name: 'Deployment Frequency',
    description: 'Average releases per day over 90-day window (DORA metric).',
    formula: 'release_count_90d / 90',
  },
  test_maturity: {
    name: 'Test Maturity',
    description: 'Weighted score across 5 testing dimensions (1-5 scale each).',
    formula: 'Sum(dimension_score * dimension_weight) / (5 * Sum(weights)), normalized to 0-1',
  },
  arch_checklist: {
    name: 'Architecture Checklist',
    description: 'Completion ratio of architecture best practices.',
    formula: 'completed_items / total_items (docs, IaC, ADRs, diagrams)',
  },
  prs_without_review: {
    name: 'PRs Without Review',
    description: 'Count of pull requests merged without any review.',
    formula: 'Count of PRs with 0 reviews at merge time',
  },
  high_vulns: {
    name: 'High Severity Vulnerabilities',
    description: 'High/critical vulnerabilities unresolved for >30 days.',
    formula: 'Count from Dependabot alerts (high + critical, open > 30 days)',
  },
};

interface DimensionDef {
  key: string;
  name: string;
  description: string;
  formula: string;
  indicators: string[];
}

export const DIMENSION_DEFINITIONS: DimensionDef[] = [
  {
    key: 'p_time',
    name: 'P_time — Schedule',
    description: 'Schedule adherence measured through earned value and milestone delivery.',
    formula: 'w_spi * normalize(SPI, ideal) + w_milestones * normalize(on_time_milestones, target)',
    indicators: ['spi', 'on_time_milestones'],
  },
  {
    key: 'p_cost',
    name: 'P_cost — Budget',
    description: 'Budget adherence measured through cost performance index and variance.',
    formula: 'w_cpi * normalize(CPI, ideal) + w_variance * normalize(budget_variance, target)',
    indicators: ['cpi', 'budget_variance'],
  },
  {
    key: 'p_quality',
    name: 'P_quality — Quality',
    description: 'Software quality across defects, governance, reviews, and failure rates.',
    formula: 'weighted_avg(defect_density, escaped_rate, mttr, story_review, governance, pr_review, change_failure_rate, post_contract_tasks)',
    indicators: ['defect_density', 'escaped_rate', 'mttr_hours', 'governance_compliance', 'story_review_ratio', 'pr_review_ratio', 'change_failure_rate', 'post_contract_tasks'],
  },
  {
    key: 'p_value',
    name: 'P_value — Strategic Value',
    description: 'Strategic impact assessment of the project.',
    formula: 'w_okr * normalize(okr_impact)',
    indicators: ['okr_impact'],
  },
  {
    key: 'p_satisfaction',
    name: 'P_satisfaction — Satisfaction',
    description: 'Stakeholder satisfaction from PM estimation and client survey.',
    formula: 'w_client * normalize(client_survey) + w_pm * normalize(pm_estimation)',
    indicators: ['pm_satisfaction', 'client_satisfaction'],
  },
  {
    key: 'p_flow',
    name: 'P_flow — Flow & Predictability',
    description: 'Development flow efficiency and predictability.',
    formula: 'weighted_avg(lead_time, commitment_reliability, pr_size, review_turnaround, deployment_frequency)',
    indicators: ['lead_time_days', 'commitment_reliability', 'pr_size_median', 'review_turnaround_hours', 'deployment_frequency'],
  },
  {
    key: 'p_engineering',
    name: 'P_engineering — Engineering Maturity',
    description: 'Engineering practices maturity across testing, reviews, and architecture.',
    formula: 'weighted_avg(test_maturity, pr_review, architecture)',
    indicators: ['test_maturity', 'pr_review_ratio', 'arch_checklist'],
  },
  {
    key: 'p_risk',
    name: 'P_risk — Risk Posture',
    description: 'Risk exposure from unreviewed code and security vulnerabilities.',
    formula: 'weighted_avg(pr_no_review_penalty, high_vulns_penalty)',
    indicators: ['prs_without_review', 'high_vulns'],
  },
];

export function buildScorecardRows(): ScorecardRowDef[] {
  const rows: ScorecardRowDef[] = [];
  rows.push({
    key: 'final_score',
    name: 'FINAL SCORE',
    description: 'Weighted aggregate of all 8 dimension scores.',
    formula: 'Sum(dimension_score * global_weight) for active dimensions',
    level: 0,
  });
  for (const dim of DIMENSION_DEFINITIONS) {
    rows.push({
      key: dim.key,
      name: dim.name,
      description: dim.description,
      formula: dim.formula,
      level: 1,
    });
    for (const indKey of dim.indicators) {
      const ind = INDICATOR_DEFINITIONS[indKey];
      rows.push({
        key: indKey,
        name: ind.name,
        description: ind.description,
        formula: ind.formula,
        level: 2,
        parentKey: dim.key,
      });
    }
  }
  return rows;
}

export const GLOBAL_WEIGHT_KEYS: Record<string, string> = {
  p_time: 'time',
  p_cost: 'cost',
  p_quality: 'quality',
  p_value: 'value',
  p_satisfaction: 'satisfaction',
  p_flow: 'flow',
  p_engineering: 'engineering',
  p_risk: 'risk',
};

export const MANUAL_KPI_FIELDS = [
  { key: 'name', label: 'Name', required: true },
  { key: 'scope', label: 'Scope', required: true },
  { key: 'responsible', label: 'Responsible', required: true },
  { key: 'methodology', label: 'Methodology', required: true },
  { key: 'formula', label: 'Formula', required: true },
  { key: 'target', label: 'Target', required: false },
  { key: 'periodicity', label: 'Periodicity', required: false },
] as const;
```

- [ ] **Step 3: Verify types compile**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to the new files (they are standalone, no imports from non-existent files yet except `RegistryRow` which exists).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/types.ts frontend/src/modules/iso-docs/components/widgets/KpiDashboard/constants.ts
git commit -m "feat(kpi-widget): add types and constants for KPI dashboard"
```

---

## Task 2: Data Hook — useKpiDashboard

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/useKpiDashboard.ts`

- [ ] **Step 1: Create the hook**

This hook combines global metrics history, scoring config, and registry rows for a given ISO cycle.

```typescript
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/useKpiDashboard.ts
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

function periodKey(year: number, month: number): string {
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

export { periodKey };
```

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/useKpiDashboard.ts
git commit -m "feat(kpi-widget): add useKpiDashboard data hook"
```

---

## Task 3: ScorecardTable Component

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ScorecardTable.tsx`
- Test: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ScorecardTable from '../ScorecardTable';
import type { GlobalMetricsRecord } from '@/modules/scorecard/types/global';
import type { MonthColumn } from '../types';

const mockMonths: MonthColumn[] = [
  { year: 2025, month: 3, label: 'Mar 2025' },
  { year: 2025, month: 4, label: 'Apr 2025' },
];

function makeIndicatorValue(value: number | null) {
  return { value, count: 5 };
}

function makeScoreValue(value: number | null) {
  return { value, count: 5 };
}

const mockRecord: GlobalMetricsRecord = {
  id: '1',
  period_year: 2025,
  period_month: 3,
  project_count: 11,
  indicators: {
    spi: makeIndicatorValue(0.8),
    cpi: makeIndicatorValue(0.8),
    on_time_milestones: makeIndicatorValue(0.7),
    defect_density: makeIndicatorValue(4.7),
    escaped_rate: makeIndicatorValue(0),
    mttr_hours: makeIndicatorValue(120),
    governance_compliance: makeIndicatorValue(0.5),
    lead_time_days: makeIndicatorValue(10),
    deployment_frequency: makeIndicatorValue(0.5),
    change_failure_rate: makeIndicatorValue(0),
    commitment_reliability: makeIndicatorValue(0.7),
    pr_review_ratio: makeIndicatorValue(0.2),
    test_maturity: makeIndicatorValue(0.6),
    arch_checklist: makeIndicatorValue(0.5),
    high_vulns: makeIndicatorValue(0),
    okr_impact: makeIndicatorValue(0.8),
    pm_satisfaction: makeIndicatorValue(0.9),
    client_satisfaction: makeIndicatorValue(0.85),
    story_review_ratio: makeIndicatorValue(0.7),
    strategic_impact: makeIndicatorValue(0.8),
  },
  scores: {
    score: makeScoreValue(68.5),
    p_time: makeScoreValue(78.9),
    p_cost: makeScoreValue(78.7),
    p_quality: makeScoreValue(73.5),
    p_value: makeScoreValue(67),
    p_satisfaction: makeScoreValue(97.6),
    p_flow: makeScoreValue(52.2),
    p_engineering: makeScoreValue(50.2),
    p_risk: makeScoreValue(50),
  },
  created_at: '2025-04-01T00:00:00Z',
  updated_at: '2025-04-01T00:00:00Z',
};

const metricsByPeriod = new Map([['2025-3', mockRecord]]);

const mockWeights = {
  time: 0.12, cost: 0.10, quality: 0.20, value: 0.05,
  satisfaction: 0.12, flow: 0.15, engineering: 0.20, risk: 0.05,
};

describe('ScorecardTable', () => {
  it('renders FINAL SCORE and dimension rows', () => {
    render(
      <ScorecardTable
        months={mockMonths}
        metricsByPeriod={metricsByPeriod}
        globalWeights={mockWeights}
        targets={{ spi: 0.8, cpi: 0.8, on_time_milestones: 1.0 } as never}
      />,
    );
    expect(screen.getByText('FINAL SCORE')).toBeInTheDocument();
    expect(screen.getByText('P_time — Schedule')).toBeInTheDocument();
    expect(screen.getByText('P_cost — Budget')).toBeInTheDocument();
  });

  it('shows score values in monthly columns', () => {
    render(
      <ScorecardTable
        months={mockMonths}
        metricsByPeriod={metricsByPeriod}
        globalWeights={mockWeights}
        targets={{} as never}
      />,
    );
    expect(screen.getByText('68.5')).toBeInTheDocument();
    expect(screen.getByText('78.9')).toBeInTheDocument();
  });

  it('collapses and expands dimensions', () => {
    render(
      <ScorecardTable
        months={mockMonths}
        metricsByPeriod={metricsByPeriod}
        globalWeights={mockWeights}
        targets={{} as never}
      />,
    );
    // Indicators should be visible by default (expanded)
    expect(screen.getByText('Schedule Performance Index')).toBeInTheDocument();

    // Click P_time to collapse
    fireEvent.click(screen.getByText('P_time — Schedule'));
    expect(screen.queryByText('Schedule Performance Index')).not.toBeInTheDocument();

    // Click again to expand
    fireEvent.click(screen.getByText('P_time — Schedule'));
    expect(screen.getByText('Schedule Performance Index')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement ScorecardTable**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ScorecardTable.tsx
import { useState, useMemo, useCallback } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/shared/lib/utils';
import type { GlobalMetricsRecord, ScoringConfig } from '@/modules/scorecard/types';
import type { MonthColumn } from './types';
import { buildScorecardRows, GLOBAL_WEIGHT_KEYS, DIMENSION_DEFINITIONS } from './constants';
import { periodKey } from './useKpiDashboard';

interface ScorecardTableProps {
  readonly months: MonthColumn[];
  readonly metricsByPeriod: Map<string, GlobalMetricsRecord>;
  readonly globalWeights: ScoringConfig['global_weights'];
  readonly targets: ScoringConfig['targets'];
}

function getScoreColor(value: number | null): string {
  if (value == null) return '';
  if (value >= 80) return 'bg-green-100 text-green-900';
  if (value >= 60) return 'bg-yellow-100 text-yellow-900';
  return 'bg-red-100 text-red-900';
}

function getIndicatorColor(value: number | null): string {
  if (value == null) return '';
  if (value >= 0.8) return 'bg-green-50 text-green-800';
  if (value >= 0.6) return 'bg-yellow-50 text-yellow-800';
  return 'bg-red-50 text-red-800';
}

function extractValue(
  record: GlobalMetricsRecord | undefined,
  key: string,
  level: number,
): number | null {
  if (!record) return null;
  if (level === 0) return record.scores.score.value != null ? Math.round(record.scores.score.value * 10) / 10 : null;
  if (level === 1) {
    const sv = record.scores[key as keyof typeof record.scores];
    return sv?.value != null ? Math.round(sv.value * 10) / 10 : null;
  }
  const iv = record.indicators[key as keyof typeof record.indicators];
  return iv?.value != null ? Math.round(iv.value * 10) / 10 : null;
}

export default function ScorecardTable({
  months,
  metricsByPeriod,
  globalWeights,
  targets,
}: ScorecardTableProps): JSX.Element {
  const rows = useMemo(() => buildScorecardRows(), []);
  const dimKeys = useMemo(() => DIMENSION_DEFINITIONS.map((d) => d.key), []);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = useCallback((dimKey: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(dimKey)) next.delete(dimKey);
      else next.add(dimKey);
      return next;
    });
  }, []);

  const getWeight = (key: string, level: number): string => {
    if (level === 0) return '';
    if (level === 1) {
      const wKey = GLOBAL_WEIGHT_KEYS[key];
      if (wKey && globalWeights) {
        const w = globalWeights[wKey as keyof typeof globalWeights];
        return w != null ? `${Math.round(w * 100)}%` : '';
      }
      return '';
    }
    return '';
  };

  const getTarget = (key: string, level: number): string => {
    if (level <= 1) return '80';
    const t = targets?.[key as keyof typeof targets];
    return t != null ? String(t) : '-';
  };

  const visibleRows = useMemo(() => {
    return rows.filter((row) => {
      if (row.level === 2 && row.parentKey && collapsed.has(row.parentKey)) return false;
      return true;
    });
  }, [rows, collapsed]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-muted/50">
            <th className="sticky left-0 z-10 bg-muted/50 text-left px-3 py-2 font-medium min-w-[250px]">Name</th>
            <th className="text-left px-3 py-2 font-medium min-w-[200px]">Formula</th>
            <th className="text-center px-3 py-2 font-medium min-w-[70px]">Target</th>
            <th className="text-center px-3 py-2 font-medium min-w-[70px]">Weight</th>
            {months.map((m) => (
              <th key={m.label} className="text-center px-3 py-2 font-medium min-w-[80px]">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => {
            const isDim = row.level === 1;
            const isExpanded = isDim && !collapsed.has(row.key);
            const isCollapsed = isDim && collapsed.has(row.key);

            return (
              <tr
                key={row.key}
                className={cn(
                  'border-b border-border/50',
                  row.level === 0 && 'font-bold bg-muted/30',
                  row.level === 1 && 'font-semibold',
                  row.level === 2 && 'text-muted-foreground',
                )}
              >
                <td
                  className={cn(
                    'sticky left-0 z-10 px-3 py-1.5',
                    row.level === 0 && 'bg-muted/30',
                    row.level === 1 && 'bg-background cursor-pointer',
                    row.level === 2 && 'bg-background pl-8',
                  )}
                  onClick={isDim ? () => toggle(row.key) : undefined}
                >
                  <span className="flex items-center gap-1">
                    {isDim && (isExpanded
                      ? <ChevronDown className="h-4 w-4 shrink-0" />
                      : <ChevronRight className="h-4 w-4 shrink-0" />
                    )}
                    {row.name}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-xs text-muted-foreground truncate max-w-[200px]" title={row.formula}>
                  {row.formula}
                </td>
                <td className="text-center px-3 py-1.5">{getTarget(row.key, row.level)}</td>
                <td className="text-center px-3 py-1.5">{getWeight(row.key, row.level)}</td>
                {months.map((m) => {
                  const record = metricsByPeriod.get(periodKey(m.year, m.month));
                  const value = extractValue(record, row.key, row.level);
                  const colorClass = row.level <= 1
                    ? getScoreColor(value)
                    : getIndicatorColor(value);

                  return (
                    <td key={m.label} className={cn('text-center px-3 py-1.5', colorClass)}>
                      {value != null ? value : '-'}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx 2>&1 | tail -10`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ScorecardTable.tsx frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ScorecardTable.test.tsx
git commit -m "feat(kpi-widget): add ScorecardTable with collapse and traffic lights"
```

---

## Task 4: AddKpiDialog Component

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/AddKpiDialog.tsx`

- [ ] **Step 1: Create AddKpiDialog**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/AddKpiDialog.tsx
import { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { MANUAL_KPI_FIELDS } from './constants';
import type { ManualKpiData } from './types';

interface AddKpiDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (data: Record<string, unknown>) => void;
  readonly isLoading: boolean;
}

const INITIAL_STATE: ManualKpiData = {
  name: '',
  scope: '',
  responsible: '',
  methodology: '',
  formula: '',
  target: null,
  periodicity: 'Mensual',
};

export default function AddKpiDialog({
  open,
  onClose,
  onSubmit,
  isLoading,
}: AddKpiDialogProps): JSX.Element {
  const [form, setForm] = useState<ManualKpiData>({ ...INITIAL_STATE });

  const handleSubmit = (): void => {
    const data: Record<string, unknown> = { ...form };
    if (form.target != null && form.target !== '') {
      data.target = Number(form.target);
    }
    onSubmit(data);
    setForm({ ...INITIAL_STATE });
  };

  const isValid = MANUAL_KPI_FIELDS
    .filter((f) => f.required)
    .every((f) => {
      const val = form[f.key as keyof ManualKpiData];
      return val != null && String(val).trim() !== '';
    });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add KPI</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {MANUAL_KPI_FIELDS.map((field) => (
            <div key={field.key} className="space-y-1">
              <Label htmlFor={field.key}>
                {field.label}{field.required && ' *'}
              </Label>
              {field.key === 'methodology' ? (
                <Textarea
                  id={field.key}
                  value={String(form[field.key as keyof ManualKpiData] ?? '')}
                  onChange={(e) => setForm((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  rows={3}
                />
              ) : (
                <Input
                  id={field.key}
                  type={field.key === 'target' ? 'number' : 'text'}
                  step={field.key === 'target' ? 'any' : undefined}
                  value={String(form[field.key as keyof ManualKpiData] ?? '')}
                  onChange={(e) => setForm((prev) => ({
                    ...prev,
                    [field.key]: field.key === 'target' ? (e.target.value === '' ? null : e.target.value) : e.target.value,
                  }))}
                />
              )}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={!isValid || isLoading}>
            {isLoading ? 'Adding...' : 'Add KPI'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/AddKpiDialog.tsx
git commit -m "feat(kpi-widget): add AddKpiDialog for manual KPI creation"
```

---

## Task 5: ManualKpiTable Component

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ManualKpiTable.tsx`
- Test: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import ManualKpiTable from '../ManualKpiTable';
import type { RegistryRow } from '../../../../types/registry';
import type { MonthColumn } from '../types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

const mockMonths: MonthColumn[] = [
  { year: 2025, month: 3, label: 'Mar 2025' },
  { year: 2025, month: 4, label: 'Apr 2025' },
];

const mockRow: RegistryRow = {
  id: 'row-1',
  node_id: 'node-1',
  year: 2025,
  row_index: 0,
  data: {
    name: '% formación seguridad',
    scope: 'Concienciación',
    responsible: 'RRHH',
    methodology: 'Porcentaje de empleados formados',
    formula: 'formados / total',
    target: 0.8,
    periodicity: 'Anual',
    m03: 0.75,
    m04: null,
  },
  created_by_id: null,
  updated_by_id: null,
  created_at: '2025-04-01T00:00:00Z',
  updated_at: '2025-04-01T00:00:00Z',
  attachments: [],
};

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe('ManualKpiTable', () => {
  it('renders manual KPI rows with data', () => {
    render(
      <Wrapper>
        <ManualKpiTable
          nodeId="node-1"
          months={mockMonths}
          rows={[mockRow]}
          isEditor
          selectedYear={2025}
        />
      </Wrapper>,
    );
    expect(screen.getByText('% formación seguridad')).toBeInTheDocument();
    expect(screen.getByText('Concienciación')).toBeInTheDocument();
    expect(screen.getByText('0.75')).toBeInTheDocument();
  });

  it('shows Add KPI button for editors', () => {
    render(
      <Wrapper>
        <ManualKpiTable
          nodeId="node-1"
          months={mockMonths}
          rows={[]}
          isEditor
          selectedYear={2025}
        />
      </Wrapper>,
    );
    expect(screen.getByText('Add KPI')).toBeInTheDocument();
  });

  it('hides Add KPI button for viewers', () => {
    render(
      <Wrapper>
        <ManualKpiTable
          nodeId="node-1"
          months={mockMonths}
          rows={[]}
          isEditor={false}
          selectedYear={2025}
        />
      </Wrapper>,
    );
    expect(screen.queryByText('Add KPI')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement ManualKpiTable**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ManualKpiTable.tsx
import { useState, useCallback } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  useCreateRegistryRow,
  useUpdateRegistryRow,
  useDeleteRegistryRow,
} from '../../../hooks/useRegistryRows';
import type { RegistryRow } from '../../../types/registry';
import type { MonthColumn } from './types';
import { monthToDataKey, MANUAL_KPI_FIELDS } from './constants';
import AddKpiDialog from './AddKpiDialog';

interface ManualKpiTableProps {
  readonly nodeId: string;
  readonly months: MonthColumn[];
  readonly rows: RegistryRow[];
  readonly isEditor: boolean;
  readonly selectedYear: number;
}

export default function ManualKpiTable({
  nodeId,
  months,
  rows,
  isEditor,
  selectedYear,
}: ManualKpiTableProps): JSX.Element {
  const [addOpen, setAddOpen] = useState(false);
  const [editingCell, setEditingCell] = useState<{ rowId: string; key: string } | null>(null);
  const [editValue, setEditValue] = useState('');

  const createRow = useCreateRegistryRow(nodeId);
  const updateRow = useUpdateRegistryRow(nodeId);
  const deleteRow = useDeleteRegistryRow(nodeId);

  const handleAdd = useCallback((data: Record<string, unknown>) => {
    createRow.mutate(
      { data, year: selectedYear },
      { onSuccess: () => setAddOpen(false) },
    );
  }, [createRow, selectedYear]);

  const handleDelete = useCallback((rowId: string) => {
    deleteRow.mutate(rowId);
  }, [deleteRow]);

  const startEdit = (rowId: string, key: string, currentValue: unknown): void => {
    setEditingCell({ rowId, key });
    setEditValue(currentValue != null ? String(currentValue) : '');
  };

  const commitEdit = (): void => {
    if (!editingCell) return;
    const numVal = editValue === '' ? null : Number(editValue);
    const val = editValue === '' ? null : (Number.isNaN(numVal) ? editValue : numVal);
    updateRow.mutate({
      rowId: editingCell.rowId,
      data: { data: { [editingCell.key]: val } },
    });
    setEditingCell(null);
  };

  const cancelEdit = (): void => {
    setEditingCell(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          KPIs Manuales
        </h3>
        {isEditor && (
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-1" /> Add KPI
          </Button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-muted/50">
              {MANUAL_KPI_FIELDS.map((f) => (
                <th
                  key={f.key}
                  className="text-left px-3 py-2 font-medium min-w-[120px]"
                >
                  {f.label}
                </th>
              ))}
              {months.map((m) => (
                <th key={m.label} className="text-center px-3 py-2 font-medium min-w-[80px]">
                  {m.label}
                </th>
              ))}
              {isEditor && <th className="w-10" />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={MANUAL_KPI_FIELDS.length + months.length + (isEditor ? 1 : 0)}
                  className="text-center py-8 text-muted-foreground"
                >
                  No manual KPIs yet.{isEditor ? ' Click "Add KPI" to create one.' : ''}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-border/50">
                {MANUAL_KPI_FIELDS.map((f) => (
                  <td key={f.key} className="px-3 py-1.5 max-w-[200px] truncate" title={String(row.data[f.key] ?? '')}>
                    {String(row.data[f.key] ?? '-')}
                  </td>
                ))}
                {months.map((m) => {
                  const key = monthToDataKey(m.month);
                  const value = row.data[key];
                  const isEditing = editingCell?.rowId === row.id && editingCell?.key === key;

                  return (
                    <td key={m.label} className="text-center px-2 py-1">
                      {isEditing ? (
                        <input
                          type="number"
                          step="any"
                          className="w-16 text-center border rounded px-1 py-0.5 text-sm"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={commitEdit}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') commitEdit();
                            if (e.key === 'Escape') cancelEdit();
                          }}
                          autoFocus
                        />
                      ) : (
                        <span
                          className={isEditor ? 'cursor-pointer hover:bg-muted/50 px-2 py-0.5 rounded' : ''}
                          onClick={isEditor ? () => startEdit(row.id, key, value) : undefined}
                        >
                          {value != null ? String(value) : '-'}
                        </span>
                      )}
                    </td>
                  );
                })}
                {isEditor && (
                  <td className="px-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      onClick={() => handleDelete(row.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AddKpiDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={handleAdd}
        isLoading={createRow.isPending}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx 2>&1 | tail -10`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ManualKpiTable.tsx frontend/src/modules/iso-docs/components/widgets/KpiDashboard/AddKpiDialog.tsx frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/ManualKpiTable.test.tsx
git commit -m "feat(kpi-widget): add ManualKpiTable with inline editing and AddKpiDialog"
```

---

## Task 6: KpiDashboard Main Component + Widget Registration

**Files:**
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/index.tsx`
- Create: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/KpiDashboard.tsx`
- Modify: `frontend/src/modules/iso-docs/components/widgets/index.ts`
- Test: `frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/KpiDashboard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/KpiDashboard.test.tsx
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';

// Mock the hooks
vi.mock('@/modules/scorecard/hooks/useGlobalMetrics', () => ({
  useGlobalMetricsHistory: () => ({ data: [], isLoading: false }),
}));
vi.mock('@/modules/scorecard/hooks/useScores', () => ({
  useScoringConfig: () => ({
    data: {
      targets: { spi: 0.8, cpi: 0.8 },
      global_weights: {
        time: 0.12, cost: 0.10, quality: 0.20, value: 0.05,
        satisfaction: 0.12, flow: 0.15, engineering: 0.20, risk: 0.05,
      },
      ideals: { spi: 1, cpi: 1 },
      constants: { sev1_cap: 60, grace_days: 5 },
      weight_validation: {},
    },
    isLoading: false,
  }),
}));
vi.mock('../../../../hooks/useRegistryRows', () => ({
  useRegistryRows: () => ({ data: [], isLoading: false }),
  useRegistryYears: () => ({ data: [2025] }),
  useCreateRegistryRow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateRegistryRow: () => ({ mutate: vi.fn() }),
  useDeleteRegistryRow: () => ({ mutate: vi.fn() }),
}));

import KpiDashboard from '../KpiDashboard';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe('KpiDashboard', () => {
  it('renders both sections', () => {
    render(
      <Wrapper>
        <KpiDashboard nodeId="node-1" isEditor />
      </Wrapper>,
    );
    expect(screen.getByText('FINAL SCORE')).toBeInTheDocument();
    expect(screen.getByText('KPIs Manuales')).toBeInTheDocument();
  });

  it('shows cycle selector', () => {
    render(
      <Wrapper>
        <KpiDashboard nodeId="node-1" isEditor={false} />
      </Wrapper>,
    );
    // Should show current or most recent cycle
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/KpiDashboard.test.tsx 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement KpiDashboard.tsx**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/KpiDashboard.tsx
import { useState, useMemo } from 'react';
import { Download } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import api from '@/core/services/client';
import type { WidgetProps } from '../index';
import ScorecardTable from './ScorecardTable';
import ManualKpiTable from './ManualKpiTable';
import { useKpiDashboard } from './useKpiDashboard';

function getCurrentCycleYear(): number {
  const now = new Date();
  return now.getMonth() >= 2 ? now.getFullYear() : now.getFullYear() - 1;
}

export default function KpiDashboard({ nodeId, isEditor }: WidgetProps): JSX.Element {
  const [selectedYear, setSelectedYear] = useState(getCurrentCycleYear);
  const {
    months,
    metricsByPeriod,
    config,
    manualRows,
    availableYears,
    isLoading,
  } = useKpiDashboard(nodeId, selectedYear);

  const yearOptions = useMemo(() => {
    const years = new Set(availableYears);
    years.add(selectedYear);
    return Array.from(years).sort((a, b) => b - a);
  }, [availableYears, selectedYear]);

  const handleExportXlsx = async (): Promise<void> => {
    const { data } = await api.get(`/iso-docs/widgets/${nodeId}/export`, {
      params: { year: selectedYear, format: 'xlsx' },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kpi_dashboard_${selectedYear}-${selectedYear + 1}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">Loading KPI data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">Ciclo:</span>
          <Select value={String(selectedYear)} onValueChange={(v) => setSelectedYear(Number(v))}>
            <SelectTrigger className="w-[140px]">
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
              <Download className="h-4 w-4 mr-1" /> Export
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={handleExportXlsx}>
              Excel (.xlsx)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Scorecard Section */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Global Scorecard
        </h3>
        <ScorecardTable
          months={months}
          metricsByPeriod={metricsByPeriod}
          globalWeights={config?.global_weights ?? { time: 0, cost: 0, quality: 0, value: 0, satisfaction: 0, flow: 0, engineering: 0, risk: 0 }}
          targets={config?.targets ?? {} as never}
        />
      </div>

      {/* Manual KPIs Section */}
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
```

- [ ] **Step 4: Create index.tsx re-export**

```tsx
// frontend/src/modules/iso-docs/components/widgets/KpiDashboard/index.tsx
export { default } from './KpiDashboard';
```

- [ ] **Step 5: Register widget in WIDGET_REGISTRY**

Modify `frontend/src/modules/iso-docs/components/widgets/index.ts`:

```typescript
import { lazy } from 'react';

export interface WidgetProps {
  readonly nodeId: string;
  readonly isEditor: boolean;
}

const KpiDashboard = lazy(() => import('./KpiDashboard'));

export const WIDGET_REGISTRY: Record<string, React.ComponentType<WidgetProps>> = {
  kpi_dashboard: KpiDashboard,
};
```

Note: Using `lazy()` so the KPI dashboard bundle doesn't load until a widget node is selected.

- [ ] **Step 6: Check that the WidgetRenderer in IsoDocs.tsx wraps in Suspense**

Read `frontend/src/modules/iso-docs/pages/IsoDocs.tsx` and check the `WidgetRenderer` function. If it doesn't wrap in `<Suspense>`, wrap the `<Widget>` call:

```tsx
import { Suspense } from 'react';

function WidgetRenderer({ widgetKey, nodeId, isEditor }: ...) {
  const Widget = WIDGET_REGISTRY[widgetKey];
  if (Widget) {
    return (
      <Suspense fallback={<div className="py-8 text-center text-muted-foreground">Loading widget...</div>}>
        <Widget nodeId={nodeId} isEditor={isEditor} />
      </Suspense>
    );
  }
  // ... fallback
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/modules/iso-docs/components/widgets/KpiDashboard/__tests__/KpiDashboard.test.tsx 2>&1 | tail -10`
Expected: 2 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/modules/iso-docs/components/widgets/KpiDashboard/ frontend/src/modules/iso-docs/components/widgets/index.ts frontend/src/modules/iso-docs/pages/IsoDocs.tsx
git commit -m "feat(kpi-widget): add KpiDashboard component and register in WIDGET_REGISTRY"
```

---

## Task 7: Backend Export Service

**Files:**
- Create: `backend/app/modules/iso_docs/services/kpi_export_service.py`
- Test: `backend/tests/iso_docs/test_widget_export.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/iso_docs/test_widget_export.py
"""Tests for KPI dashboard widget export."""
import io

import openpyxl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.iso_docs.services.kpi_export_service import KpiExportService


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_target = MagicMock(side_effect=lambda k: {"spi": 0.8, "cpi": 0.8}.get(k, 0))
    config.get_constant = MagicMock(side_effect=lambda k: {"threshold_green": 80, "threshold_yellow": 60}.get(k, 0))
    config.global_weights = MagicMock()
    config.global_weights.time = 0.12
    config.global_weights.cost = 0.10
    config.global_weights.quality = 0.20
    config.global_weights.value = 0.05
    config.global_weights.satisfaction = 0.12
    config.global_weights.flow = 0.15
    config.global_weights.engineering = 0.20
    config.global_weights.risk = 0.05
    return config


def test_generates_xlsx_with_two_sheets(mock_config):
    """Export produces XLSX with Global Scorecard and Manual KPIs sheets."""
    service = KpiExportService(mock_config)

    # Empty data — just verify structure
    buf = service.build_xlsx(
        global_by_period={},
        manual_rows=[],
        start_year=2025,
        start_month=3,
        end_year=2026,
        end_month=2,
    )

    wb = openpyxl.load_workbook(buf)
    assert "Global Scorecard" in wb.sheetnames
    assert "KPIs manuales" in wb.sheetnames


def test_scorecard_sheet_has_metric_rows(mock_config):
    """Scorecard sheet includes FINAL SCORE and dimension rows."""
    service = KpiExportService(mock_config)
    buf = service.build_xlsx(
        global_by_period={},
        manual_rows=[],
        start_year=2025,
        start_month=3,
        end_year=2026,
        end_month=2,
    )

    wb = openpyxl.load_workbook(buf)
    ws = wb["Global Scorecard"]
    values = [row[0].value for row in ws.iter_rows(min_col=1, max_col=1)]
    assert any("FINAL SCORE" in str(v) for v in values if v)
    assert any("P_time" in str(v) for v in values if v)


def test_manual_kpis_sheet_with_rows(mock_config):
    """Manual KPIs sheet includes row data."""
    mock_row = MagicMock()
    mock_row.data = {
        "name": "% formación seguridad",
        "scope": "Concienciación",
        "responsible": "RRHH",
        "methodology": "Porcentaje formados",
        "formula": "formados / total",
        "target": 0.8,
        "periodicity": "Anual",
        "m03": 0.75,
        "m04": None,
    }

    service = KpiExportService(mock_config)
    buf = service.build_xlsx(
        global_by_period={},
        manual_rows=[mock_row],
        start_year=2025,
        start_month=3,
        end_year=2026,
        end_month=2,
    )

    wb = openpyxl.load_workbook(buf)
    ws = wb["KPIs manuales"]
    values = []
    for row in ws.iter_rows(values_only=True):
        values.append(list(row))
    # Header + 1 data row
    assert len(values) >= 2
    assert "% formación seguridad" in values[1]


def test_month_columns_follow_iso_cycle(mock_config):
    """Month columns go Mar 2025 → Feb 2026."""
    service = KpiExportService(mock_config)
    buf = service.build_xlsx(
        global_by_period={},
        manual_rows=[],
        start_year=2025,
        start_month=3,
        end_year=2026,
        end_month=2,
    )

    wb = openpyxl.load_workbook(buf)
    ws = wb["KPIs manuales"]
    header = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    assert "Mar 2025" in header
    assert "Feb 2026" in header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/iso_docs/test_widget_export.py -v 2>&1 | tail -10`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement KpiExportService**

```python
# backend/app/modules/iso_docs/services/kpi_export_service.py
"""XLSX export for the KPI Dashboard widget."""

from __future__ import annotations

import calendar
from io import BytesIO

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.config import ScoringConfig
from app.core.services.export_helpers import (
    THIN_BORDER,
    apply_header_style,
    apply_indicator_traffic_light,
    apply_score_traffic_light,
    format_month_header,
    freeze_panes,
    save_to_bytes,
    set_column_widths,
    DEFAULT_GREEN_THRESHOLD,
    DEFAULT_YELLOW_THRESHOLD,
)
from app.modules.scorecard.models.global_metrics import GlobalMetricsRecord
from app.modules.scorecard.services.export_definitions import get_metric_rows

MANUAL_KPI_FIELDS = [
    "name", "scope", "responsible", "methodology",
    "formula", "target", "periodicity",
]
MANUAL_KPI_HEADERS = [
    "Name", "Scope", "Responsible", "Methodology",
    "Formula", "Target", "Periodicity",
]


class KpiExportService:
    """Generates XLSX with scorecard + manual KPIs for ISO audits."""

    def __init__(self, config: ScoringConfig):
        self.config = config
        self._green = self._get_threshold("threshold_green", DEFAULT_GREEN_THRESHOLD)
        self._yellow = self._get_threshold("threshold_yellow", DEFAULT_YELLOW_THRESHOLD)

    def build_xlsx(
        self,
        *,
        global_by_period: dict[tuple[int, int], GlobalMetricsRecord | None],
        manual_rows: list,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> BytesIO:
        periods = self._generate_periods(start_year, start_month, end_year, end_month)

        wb = Workbook()
        wb.remove(wb.active)

        ws_sc = wb.create_sheet("Global Scorecard")
        self._write_scorecard_sheet(ws_sc, periods, global_by_period)

        ws_kpi = wb.create_sheet("KPIs manuales")
        self._write_manual_kpis_sheet(ws_kpi, periods, manual_rows)

        return save_to_bytes(wb)

    def _write_scorecard_sheet(
        self,
        ws,
        periods: list[tuple[int, int]],
        global_by_period: dict[tuple[int, int], GlobalMetricsRecord | None],
    ) -> None:
        cycle_label = f"{periods[0][0]}–{periods[-1][0]}" if periods else ""
        ws.append([f"Global Dashboard — Ciclo {cycle_label}"])
        ws.append([])

        header = ["Name", "Description", "Formula", "Target"]
        for y, m in periods:
            header.append(format_month_header(y, m))
        ws.append(header)
        apply_header_style(ws, ws.max_row)

        metric_rows = get_metric_rows()
        for mr in metric_rows:
            level = mr["level"]
            indent = "  " * level
            target = self._get_target_for_metric(mr["key"], level)

            row_data = [
                f"{indent}{mr['name']}",
                mr["description"],
                mr["formula"],
                target if target else "-",
            ]

            for period in periods:
                row_data.append(
                    self._extract_global_value(mr["key"], level, global_by_period.get(period))
                )

            ws.append(row_data)
            current_row = ws.max_row

            for col_idx in range(5, 5 + len(periods)):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                if level <= 1:
                    apply_score_traffic_light(cell, cell.value, self._green, self._yellow)
                else:
                    apply_indicator_traffic_light(
                        cell, cell.value, self._green / 100, self._yellow / 100,
                    )

        widths = {"A": 35, "B": 50, "C": 45, "D": 12}
        for i in range(len(periods)):
            widths[get_column_letter(5 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 4, 5)

    def _write_manual_kpis_sheet(
        self,
        ws,
        periods: list[tuple[int, int]],
        manual_rows: list,
    ) -> None:
        header = list(MANUAL_KPI_HEADERS)
        for y, m in periods:
            header.append(format_month_header(y, m))
        ws.append(header)
        apply_header_style(ws, ws.max_row)

        for row in manual_rows:
            data = row.data if hasattr(row, "data") else row
            row_values = [data.get(f, "") for f in MANUAL_KPI_FIELDS]
            for _y, m in periods:
                key = f"m{m:02d}"
                row_values.append(data.get(key))
            ws.append(row_values)

        widths = {
            "A": 30, "B": 15, "C": 15, "D": 40, "E": 30, "F": 10, "G": 12,
        }
        for i in range(len(periods)):
            widths[get_column_letter(8 + i)] = 12
        set_column_widths(ws, widths)
        freeze_panes(ws, 2, 8)

    def _get_threshold(self, name: str, default: float) -> float:
        try:
            val = self.config.get_constant(name)
            return val if val > 0 else default
        except (KeyError, ValueError):
            return default

    def _get_target_for_metric(self, key: str, level: int) -> str | None:
        if level <= 1:
            return str(int(self._green))
        try:
            return str(self.config.get_target(key))
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _extract_global_value(
        key: str, level: int, record: GlobalMetricsRecord | None,
    ) -> float | None:
        if record is None:
            return None
        if level == 0:
            val = record.scores.score.value
            return round(val, 1) if val is not None else None
        if level == 1:
            score_val = getattr(record.scores, key, None)
            if score_val and score_val.value is not None:
                return round(score_val.value, 1)
            return None
        indicator_val = getattr(record.indicators, key, None)
        if indicator_val and indicator_val.value is not None:
            return round(indicator_val.value, 1)
        return None

    @staticmethod
    def _generate_periods(
        start_year: int, start_month: int, end_year: int, end_month: int,
    ) -> list[tuple[int, int]]:
        periods: list[tuple[int, int]] = []
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            periods.append((year, month))
            month += 1
            if month > 12:
                month = 1
                year += 1
        return periods
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/iso_docs/test_widget_export.py -v 2>&1 | tail -10`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/iso_docs/services/kpi_export_service.py backend/tests/iso_docs/test_widget_export.py
git commit -m "feat(kpi-widget): add KpiExportService for XLSX generation"
```

---

## Task 8: Backend Export Endpoint + Router

**Files:**
- Create: `backend/app/modules/iso_docs/api/widget_export.py`
- Modify: `backend/app/modules/iso_docs/router.py`

- [ ] **Step 1: Create the export endpoint**

```python
# backend/app/modules/iso_docs/api/widget_export.py
"""Widget export endpoints for ISO Docs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select, tuple_

from app.core.api.deps import CurrentUser, DBSession, ScoringConfigDep, limiter
from app.core.services.export_helpers import XLSX_MEDIA_TYPE
from app.modules.iso_docs.api.deps import check_user_access
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.scorecard.models.global_metrics import (
    GlobalMetricsDB,
    GlobalMetricsRecord,
)
from app.modules.iso_docs.services.kpi_export_service import KpiExportService

logger = structlog.get_logger()

router = APIRouter()


def _iso_cycle_periods(year: int) -> tuple[int, int, int, int]:
    """Return (start_year, start_month, end_year, end_month) for an ISO cycle."""
    return year, 3, year + 1, 2


@router.get(
    "/widgets/{node_id}/export",
    responses={404: {"description": "Widget node not found"}},
)
@limiter.limit("10/minute")
async def export_kpi_dashboard(
    request: Request,
    node_id: UUID,
    db: DBSession,
    user: CurrentUser,
    config: ScoringConfigDep,
    year: Annotated[int, Query(description="ISO cycle year (e.g. 2025 = Mar 2025 – Feb 2026)")],
    format: Annotated[str, Query()] = "xlsx",
) -> Response:
    await check_user_access(db, node_id, user)

    node_result = await db.execute(
        select(IsoDocNodeDB).where(
            IsoDocNodeDB.id == node_id,
            IsoDocNodeDB.type == "widget",
        )
    )
    node = node_result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Widget node not found")

    start_year, start_month, end_year, end_month = _iso_cycle_periods(year)

    # Fetch global metrics
    periods = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        periods.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    global_result = await db.execute(
        select(GlobalMetricsDB).where(
            tuple_(GlobalMetricsDB.period_year, GlobalMetricsDB.period_month).in_(periods)
        )
    )
    global_by_period: dict[tuple[int, int], GlobalMetricsRecord | None] = dict.fromkeys(periods)
    for row in global_result.scalars():
        key = (row.period_year, row.period_month)
        if key in global_by_period:
            global_by_period[key] = GlobalMetricsRecord.from_db(row)

    # Fetch manual KPI rows
    rows_result = await db.execute(
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node_id, RegistryRowDB.year == year)
        .order_by(RegistryRowDB.row_index)
    )
    manual_rows = list(rows_result.scalars())

    service = KpiExportService(config)
    output = service.build_xlsx(
        global_by_period=global_by_period,
        manual_rows=manual_rows,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    filename = f"kpi_dashboard_{year}-{year + 1}.xlsx"
    logger.info("kpi_widget_exported", node_id=str(node_id), year=year)

    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 2: Mount the router**

Modify `backend/app/modules/iso_docs/router.py` — add after the last `include_router`:

```python
from app.modules.iso_docs.api.widget_export import router as widget_export_router

router.include_router(widget_export_router)
```

- [ ] **Step 3: Verify the app starts**

Run: `cd backend && python -c "from app.main import app; print('OK')" 2>&1 | tail -5`
Expected: `OK` — no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/iso_docs/api/widget_export.py backend/app/modules/iso_docs/router.py
git commit -m "feat(kpi-widget): add widget export endpoint and mount router"
```

---

## Task 9: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/iso_docs/ -v 2>&1 | tail -20`
Expected: All tests pass, including new `test_widget_export.py`.

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run src/modules/iso-docs/ 2>&1 | tail -20`
Expected: All tests pass, including new widget tests.

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | tail -10`
Expected: No type errors.

- [ ] **Step 4: Fix any failures**

If tests fail, read the error output and fix. Common issues:
- Missing imports (check paths)
- Mock shape doesn't match actual type (update mock)
- Widget lazy loading needs Suspense boundary (verify step 6.6 was done)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test(kpi-widget): verify all tests pass after integration"
```
