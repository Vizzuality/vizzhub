# Migration Plan: Google Sheets → FastAPI + React

This document maps the legacy Google Sheets + Google Apps Script implementation to the new FastAPI + React architecture.

## Architecture Overview

```
Legacy System                    New System
┌─────────────────┐             ┌─────────────────┐
│  Google Sheets  │             │  PostgreSQL/    │
│  - Data_Forms   │     →       │  SQLite         │
│  - Params       │             │  - projects     │
│  - Data         │             │  - metrics      │
│  - Scores       │             │  - (computed)   │
└─────────────────┘             └─────────────────┘
        ↓                               ↓
┌─────────────────┐             ┌─────────────────┐
│  Apps Script    │             │  FastAPI        │
│  - Collectors   │     →       │  - Collectors   │
│  - Formulas     │             │  - Normalizers  │
└─────────────────┘             │  - Calculators  │
                                └─────────────────┘
                                        ↓
                                ┌─────────────────┐
                                │  React + Vite   │
                                │  - Dashboard    │
                                │  - ScoreCard    │
                                │  - Forms        │
                                └─────────────────┘
```

---

## Sheet-to-Component Mapping

### 1. Params Sheet → `scoring_config.yaml` + `ScoringConfig` class

| Legacy Location | New Location | Notes |
|-----------------|--------------|-------|
| Named ranges (targets) | `scoring_config.yaml` → `targets` | Same values |
| Weight groups | `scoring_config.yaml` → `weights` | Organized by dimension |
| Constants | `scoring_config.yaml` → `constants` | `sev1_cap`, `grace_days` |
| Validators | `ScoringConfig.validate_weights()` | Programmatic validation |

### 2. Data_Forms Sheet → `metrics` table + `MetricsCreate` model

| Legacy Field | New Field | Source |
|--------------|-----------|--------|
| Project Name | `projects.name` | Manual |
| Jira ID | `projects.jira_project_key` | Manual |
| GitHub Repo | `projects.github_repo` | Manual |
| EVM (B8-B15) | `metrics.evm_data` | Manual |
| Milestones (B25+) | `metrics.milestones` | Manual |
| Defects (B47-B49) | `metrics.jira_defects` | Jira API |
| Escaped (B58-B59) | `metrics.jira_defects` | Jira API |
| MTTR (B68-B69) | `metrics.jira_defects` | Jira API |
| Governance (B78) | `metrics.governance_exceptions` | Manual |
| PM Satisfaction (B87-B89) | `metrics.pm_satisfaction` | Manual |
| Test Maturity (B98-B102) | `metrics.test_maturity` | Manual |
| Flow (B111-B129) | `metrics.flow_metrics` | Jira API |
| GitHub (B138-B158) | `metrics.github_metrics` | GitHub API |
| Architecture (B167-B170) | `metrics.architecture` | Manual |
| Story Review (B179-B180) | `metrics.flow_metrics` | Jira API |
| Strategic Impact (B190) | `metrics.strategic_impact` | Manual |
| Client Survey (B199-B206) | `metrics.client_survey` | Manual |

### 3. Data Sheet → `IndicatorNormalizer` service (computed on-the-fly)

| Legacy Column | Python Function | Location |
|---------------|-----------------|----------|
| A: SPI | `_normalize_spi()` | `normalizers/indicators.py` |
| B: OnTimeMilestones | `_normalize_milestones()` | `normalizers/indicators.py` |
| C: CPI | `_normalize_cpi()` | `normalizers/indicators.py` |
| D: BudgetVariance | `_calculate_budget_variance()` | `normalizers/indicators.py` |
| E: PM_Satisfaction | `_normalize_pm_satisfaction()` | `normalizers/indicators.py` |
| F: DefectDensity | `_calculate_defect_density()` | `normalizers/indicators.py` |
| G: GovernanceCompliance | `_normalize_governance()` | `normalizers/indicators.py` |
| H: EscapedRate | `_calculate_escaped_rate()` | `normalizers/indicators.py` |
| I: MTTR | `_get_mttr()` | `normalizers/indicators.py` |
| J: TestMaturity | `_normalize_test_maturity()` | `normalizers/indicators.py` |
| K: LeadTime | `_get_lead_time()` | `normalizers/indicators.py` |
| L: FlowEfficiency | `_get_flow_efficiency()` | `normalizers/indicators.py` |
| M: CommitmentReliability | `_get_commitment_reliability()` | `normalizers/indicators.py` |
| N: PRsWithoutReview | `_get_prs_without_review()` | `normalizers/indicators.py` |
| O: HighVuln | `_get_high_vulns()` | `normalizers/indicators.py` |
| P: PR_review_ratio | `_get_pr_review_ratio()` | `normalizers/indicators.py` |
| Q: ArchChecklist | `_normalize_architecture()` | `normalizers/indicators.py` |
| R: StoriesWithReviewer | `_calculate_story_review_ratio()` | `normalizers/indicators.py` |
| S: OKR_Impact | `_normalize_okr_impact()` | `normalizers/indicators.py` |
| T: ClientSatisfaction | `_normalize_client_survey()` | `normalizers/indicators.py` |

### 4. Scores Sheet → Dimension Calculators (computed on-the-fly)

| Legacy Formula | Python Class | Location |
|----------------|--------------|----------|
| P_time | `TimeCalculator` | `calculators/dimensions.py` |
| P_cost | `CostCalculator` | `calculators/dimensions.py` |
| P_quality | `QualityCalculator` | `calculators/dimensions.py` |
| P_value | `ValueCalculator` | `calculators/dimensions.py` |
| P_satisfaction | `SatisfactionCalculator` | `calculators/dimensions.py` |
| P_flow | `FlowCalculator` | `calculators/dimensions.py` |
| P_engineering | `EngineeringCalculator` | `calculators/dimensions.py` |
| P_risk | `RiskCalculator` | `calculators/dimensions.py` |
| Final Score | `FinalScoreCalculator` | `calculators/final_score.py` |

---

## Formula-to-Function Mapping

### Normalization Patterns

| Pattern | Legacy Excel | Python Function |
|---------|--------------|-----------------|
| Higher is better | `MIN(1, value)` | `normalize_higher_is_better()` |
| Lower is better | `MIN(1, target/MAX(value, 0.001))` | `normalize_lower_is_better()` |
| Missing → neutral | `IF(ISBLANK(x), 0.5, ...)` | `_safe_value()` returns 0.5 |
| Strict zero target | `IF(t=0, IF(v=0,1,0), ...)` | `normalize_strict_zero_target()` |

### Key Formula Translations

**SPI Calculation:**
```excel
# Legacy
=IF(B11>0, B10/B11, NA())

# Python
def _normalize_spi(self, evm: EVMData | None) -> float | None:
    if evm is None or evm.percent_planned <= 0:
        return None
    return evm.percent_completed / evm.percent_planned
```

**CPI Calculation:**
```excel
# Legacy
=IF(B9>0, B13/B9, NA())

# Python
def _normalize_cpi(self, evm: EVMData | None) -> float | None:
    if evm is None or evm.cost_to_date <= 0:
        return None
    ev = evm.budget_total * evm.percent_completed
    return ev / evm.cost_to_date
```

**P_quality with Sev1 Cap:**
```excel
# Legacy (conceptual)
=IF(Sev1_in_prod, MIN(score, Sev1_cap), score)

# Python
def calculate(self, indicators, sev1_incident=False) -> int:
    score = self._to_score(weighted_sum)
    if sev1_incident:
        sev1_cap = int(self.config.get_constant("sev1_cap"))
        score = min(score, sev1_cap)
    return score
```

**On-Time Milestones:**
```excel
# Legacy
=SUM(H26:H37) / SUM(G26:G37)

# Python
def _normalize_milestones(self, milestones: list[Milestone] | None) -> float | None:
    # ... grace_days calculation
    return weighted_on_time / total_weight
```

---

## Database Schema

### projects table
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    jira_project_key VARCHAR(50),
    github_repo VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### metrics table
```sql
CREATE TABLE metrics (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    evm_data JSON,
    milestones JSON,
    jira_defects JSON,
    flow_metrics JSON,
    github_metrics JSON,
    test_maturity JSON,
    architecture JSON,
    pm_satisfaction JSON,
    client_survey JSON,
    strategic_impact VARCHAR(50),
    governance_exceptions INTEGER,
    sev1_incident BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);
```

### Note: Indicators and Scores
Indicators and scores are computed on-the-fly rather than stored, following the legacy pattern where formulas calculate values dynamically. This ensures:
- No stale data
- Configuration changes apply immediately
- Audit trail via metrics table

---

## API Endpoint Mapping

| Operation | Endpoint | Method |
|-----------|----------|--------|
| List projects | `/api/scorecards` | GET |
| Create project | `/api/scorecards` | POST |
| Get project | `/api/scorecards/{id}` | GET |
| Update project | `/api/scorecards/{id}` | PATCH |
| Delete project | `/api/scorecards/{id}` | DELETE |
| Add metrics | `/api/metrics/project/{id}` | POST |
| Get latest metrics | `/api/metrics/project/{id}/latest` | GET |
| Calculate scores (ad-hoc) | `/api/scores/calculate` | POST |
| Get project scores | `/api/scores/project/{id}` | GET |
| Get score history | `/api/scores/project/{id}/history` | GET |
| Get configuration | `/api/config` | GET |
| Validate configuration | `/api/config/validate` | GET |

---

## Data Source Integration

### Jira API (JiraCollector)
- Defect counts: JQL queries for bugs
- Task counts: JQL queries for stories/tasks
- Escaped defects: JQL with environment filter
- MTTR: Custom field or incident tracking
- Flow metrics: Issue transition times
- Story reviewer: Custom field check

### GitHub API (GitHubCollector)
- PR review ratio: `/repos/{repo}/pulls` + `/pulls/{n}/reviews`
- PRs without review: Count of merged PRs with no reviews
- High vulns: `/repos/{repo}/dependabot/alerts` (>30 days old)

### Manual Inputs (via API)
- EVM data (budget, costs, completion)
- Milestones (planned/actual dates)
- Architecture checklist
- Test maturity ratings
- PM satisfaction estimation
- Client survey responses
- Strategic impact selection
- Governance exceptions

---

## Configuration Migration

### Named Ranges → YAML

Legacy named ranges are now in `scoring_config.yaml`:

```yaml
# Example mapping
targets:
  defect_density: 3      # DefDensity_t
  escaped_rate: 0.01     # Escaped_t
  mttr_hours: 24         # MTTR_t
  spi: 1                 # SPI_t
  cpi: 1                 # CPI_t
  lead_time_days: 3      # LT_t
  flow_efficiency: 0.4   # FE_t
  high_vuln_count: 0     # HighVuln_t
  gov_exceptions: 2      # GovExc_t
  pr_no_review_ratio: 0.02  # PR_noReview_t

weights:
  global:
    time: 0.12           # W_time
    cost: 0.10           # W_cost
    # ... etc
```

---

## Testing Strategy

1. **Unit Tests** (`tests/test_normalizers.py`)
   - Test each normalization pattern
   - Verify edge cases (None, zero, negative)
   - Confirm neutral value handling

2. **Calculator Tests** (`tests/test_calculators.py`)
   - Test each dimension calculator
   - Verify weight application
   - Test Sev1 cap behavior
   - Test final score aggregation

3. **API Tests** (`tests/test_api.py`)
   - Test CRUD operations
   - Test score calculation endpoint
   - Test configuration endpoint

4. **Integration Tests**
   - End-to-end metric input → score output
   - Compare with legacy spreadsheet results

---

## Migration Checklist

- [x] Create project structure
- [x] Implement scoring configuration loader
- [x] Implement normalizer patterns (base.py)
- [x] Implement indicator normalizer service
- [x] Implement dimension calculators
- [x] Implement final score calculator
- [x] Create database models
- [x] Implement API endpoints
- [x] Create React frontend skeleton
- [x] Implement scorecard visualization
- [x] Implement radar chart for dimensions
- [ ] Create data collectors for Jira
- [ ] Create data collectors for GitHub
- [ ] Create metrics input forms
- [ ] Add authentication
- [ ] Add score history tracking
- [ ] Create comparison views
- [ ] Production deployment

---

## Key Differences from Legacy

1. **Computed vs Stored**: Indicators and scores are computed on-the-fly rather than stored in cells
2. **API-First**: All operations go through REST API
3. **Type Safety**: Python type hints + Pydantic validation
4. **Separation**: Collectors, normalizers, and calculators are distinct services
5. **Testability**: Dependency injection allows easy mocking
6. **Configuration**: YAML file instead of sheet cells
