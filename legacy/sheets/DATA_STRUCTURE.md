# Data Structure

Hoja de indicadores normalizados. Todos los valores están en escala 0-1 o 0-100 según el tipo.

## Row Layout

- **Row 1**: Column headers (indicator names)
- **Row 2**: Calculated values (formulas referencing Data_Forms)
- **Row 4**: Descriptions
- **Row 5**: Formulas/definitions
- **Row 6**: Dimension mapping (which P_* uses this indicator)

## Indicators

### Column A: SPI
- **Description**: Schedule Performance Index
- **Formula**: `=Data_Forms!B15`
- **Source**: EVM calculation
- **Used in**: P_time
- **Range**: 0-∞ (normalized to target in Scores)

### Column B: OnTimeMilestones_0to1
- **Description**: Percentage of milestones delivered on time (weighted)
- **Formula**: `=Data_Forms!B24`
- **Source**: Milestone tracking
- **Used in**: P_time
- **Range**: 0-1

### Column C: CPI
- **Description**: Cost Performance Index
- **Formula**: `=Data_Forms!B14`
- **Source**: EVM calculation
- **Used in**: P_cost
- **Range**: 0-∞ (normalized to target in Scores)

### Column D: BudgetVariance_OverrunPct
- **Description**: Percentage by which Actual Cost exceeds Budget
- **Formula**: `=IF(Data_Forms!B8=0, 0, MAX(0, Data_Forms!B9/Data_Forms!B8 - 1))`
- **Source**: EVM calculation
- **Used in**: P_cost
- **Range**: 0-∞ (0 = on/under budget)

### Column E: PM_ClientSatisfaction_0to1
- **Description**: Composite PM estimation of client satisfaction
- **Formula**:
```excel
=ROUND(
  0.3 * IF(delivery_complaints="no", 1, IF(delivery_complaints="yes", 0.4, 0.75)) +
  0.3 * IF(design_complaints="no", 1, IF(design_complaints="yes", 0.4, 0.75)) +
  0.4 * IF(ISBLANK(overall_estimation), 0.5, overall_estimation/5),
2)
```
- **Used in**: P_satisfaction
- **Range**: 0-1

### Column F: DefectDensity_per_100Tasks
- **Description**: Number of defects found per 100 tasks
- **Formula**: `=Data_Forms!B49`
- **Source**: Jira
- **Used in**: P_quality
- **Range**: 0-∞ (lower is better)

### Column G: GovernanceCompliance_score_0to100
- **Description**: Score based on peer review exceptions
- **Formula**: `=MAX(0, 1 - (exceptions / GovExc_t))`
- **Source**: Manual input
- **Used in**: P_quality
- **Range**: 0-1 (1 = full compliance)

### Column H: EscapedRate_per_100Tasks
- **Description**: Bugs escaped to production per 100 tasks
- **Formula**: `=Data_Forms!B58`
- **Source**: Jira
- **Used in**: P_quality
- **Range**: 0-∞ (lower is better)

### Column I: MTTR_hours
- **Description**: Mean time to recover from incidents
- **Formula**: `=Data_Forms!B68`
- **Source**: Jira
- **Used in**: P_quality
- **Range**: 0-∞ (lower is better)

### Column J: TestMaturity_percent
- **Description**: Weighted test coverage maturity
- **Formula**:
```excel
=ROUND(
  W_test_e2e * IF(ISBLANK(e2e), 0.5, e2e/5) +
  W_test_unit * IF(ISBLANK(unit), 0.5, unit/5) +
  W_test_access * IF(ISBLANK(access), 0.5, access/5) +
  W_test_security * IF(ISBLANK(security), 0.5, security/5) +
  W_test_frontend * IF(ISBLANK(frontend), 0.5, frontend/5),
2)
```
- **Used in**: P_engineering
- **Range**: 0-1

### Column K: LeadTime_days
- **Description**: Average days from To Do to Done
- **Formula**: `=Data_Forms!B111`
- **Source**: Jira
- **Used in**: P_flow
- **Range**: 0-∞ (lower is better)

### Column L: FlowEfficiency_0to1
- **Description**: Active work time / Total elapsed time
- **Formula**: `=Data_Forms!B120`
- **Source**: Jira
- **Used in**: P_flow
- **Range**: 0-1 (higher is better)

### Column M: CommitmentReliability_0to1
- **Description**: Completed / Committed issues ratio
- **Formula**: `=Data_Forms!B129`
- **Source**: Jira
- **Used in**: P_flow
- **Range**: 0-1

### Column N: PRsWithoutReview_count
- **Description**: Number of PRs merged without review
- **Formula**: `=Data_Forms!B138`
- **Source**: GitHub API
- **Used in**: P_risk
- **Range**: 0-∞ (lower is better)

### Column O: HighVuln_open_gt30d
- **Description**: High-severity vulnerabilities open >30 days
- **Formula**: `=Data_Forms!B158`
- **Source**: GitHub Dependabot
- **Used in**: P_risk
- **Range**: 0-∞ (lower is better)

### Column P: PR_review_ratio_0to1
- **Description**: Ratio of PRs with at least 1 review
- **Formula**: `=Data_Forms!B148`
- **Source**: GitHub API
- **Used in**: P_engineering, P_quality
- **Range**: 0-1

### Column Q: ArchChecklist_0to4
- **Description**: Sum of architecture checklist items
- **Formula**:
```excel
=SUM(
  IF(arch_docs, 1, 0),
  IF(iac, 1, 0),
  IF(adrs, 1, 0),
  IF(diagrams, 1, 0)
)
```
- **Used in**: P_engineering
- **Range**: 0-4 (normalized to 0-1 in calculator)

### Column R: StoriesWithoutReviewer_ratio_0to1
- **Description**: Ratio of stories with at least 1 reviewer
- **Formula**:
```excel
=IFERROR(
  IF(total_stories = 0, 0,
     MIN(1, MAX(0, stories_with_reviewer / total_stories))
  ),
0)
```
- **Used in**: P_quality
- **Range**: 0-1

### Column S: OKR_Impact_0to100
- **Description**: Strategic impact score from dropdown
- **Formula**:
```excel
=SWITCH(
  TRUE,
  REGEXMATCH(input, "low"), 0.25,
  REGEXMATCH(input, "moderate"), 0.55,
  REGEXMATCH(input, "high"), 0.8,
  REGEXMATCH(input, "transform"), 1,
  0.5  -- neutral default
)
```
- **Used in**: P_value
- **Range**: 0-1 (mapped from categorical)

### Column T: ClientSatisfaction
- **Description**: End-of-project client survey score
- **Source**: Manual (survey)
- **Used in**: P_satisfaction
- **Range**: 0-1 (weighted average of survey questions)
- **Note**: End of project indicator only

---

## Neutral Value Rules

When an indicator is blank (data not yet available):
- Most indicators use **0.5** as neutral
- This prevents penalizing in-progress projects
- Once data exists, actual values are used

When a governance tool is disabled:
- **Penalize** (use worst-case value)
- Example: Dependabot disabled → HighVuln = worst case
