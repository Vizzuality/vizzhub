# Scores Structure

Hoja de scores por dimensión y score final. Todas las fórmulas producen valores 0-100.

## Row Layout

- **Row 1**: Dimension names (P_time, P_cost, etc.)
- **Row 2**: Calculated scores (0-100)
- **Row 3**: Descriptions
- **Row 10**: Final Score (Total Score)

---

## Dimension Scores

### P_time (Column A)
**Schedule adherence score**

```excel
=ROUND(100 * (
  W_time_spi * MIN(1, IF(ISBLANK(SPI), 0.5, SPI / SPI_t)) +
  W_time_milestones * MIN(1, IF(ISBLANK(OnTimeMilestones), 0.5, OnTimeMilestones))
), 0)
```

**Components:**
- SPI normalized to target (capped at 1)
- On-time milestones ratio (already 0-1)

**Weights (default):**
- W_time_spi: 0.6
- W_time_milestones: 0.4

---

### P_cost (Column B)
**Budget adherence score**

```excel
=ROUND(100 * (
  W_cost_cpi * MIN(1, IF(ISBLANK(CPI), 0.5, CPI / CPI_t)) +
  W_cost_var * MAX(0, IF(ISBLANK(BudgetVariance), 0.5, 1 - BudgetVariance))
), 0)
```

**Components:**
- CPI normalized to target (capped at 1)
- Budget variance inverted (1 - overrun%, floored at 0)

**Weights (default):**
- W_cost_cpi: 0.7
- W_cost_var: 0.3

---

### P_quality (Column C)
**Product & delivery quality score**

```excel
=ROUND(100 * (
  W_def * IF(ISBLANK(DefectDensity), 0.5, MIN(1, DefDensity_t / MAX(DefectDensity, 0.001))) +
  W_qual_gov * IF(ISBLANK(GovCompliance), 0.5, GovCompliance) +
  W_esc * IF(ISBLANK(EscapedRate), 0.5, MIN(1, Escaped_t / MAX(EscapedRate, 0.001))) +
  W_mttr * IF(ISBLANK(MTTR), 0.5, MIN(1, MTTR_t / MAX(MTTR, 0.001))) +
  W_q_pr * IF(ISBLANK(PR_review_ratio), 0.5, PR_review_ratio) +
  W_q_storyrev * IF(ISBLANK(StoriesWithReviewer), 0.5, StoriesWithReviewer)
), 0)
```

**Components:**
- Defect density (inverted, lower is better)
- Governance compliance (direct, higher is better)
- Escaped rate (inverted, lower is better)
- MTTR (inverted, lower is better)
- PR review ratio (direct, higher is better)
- Story review ratio (direct, higher is better)

**Weights (default):**
- W_def: 0.05
- W_esc: 0.20
- W_mttr: 0.05
- W_q_storyrev: 0.30
- W_qual_gov: 0.30
- W_q_pr: 0.10

**Special rule:** If Sev1 incident occurred, cap score at Sev1_cap (60).

---

### P_value (Column D)
**Strategic/business value score**

```excel
=ROUND(100 * IF(ISBLANK(OKR_Impact), 0.5, OKR_Impact / 100), 0)
```

**Components:**
- OKR Impact score (categorical → numeric)

**Note:** ROI was intentionally removed to avoid double-counting with CPI/SPI.

---

### P_satisfaction (Column E)
**Client satisfaction score**

```excel
=ROUND(100 * IF(
  NOT(ISBLANK(ClientSurvey)),
  W_sat_client * ClientSurvey + W_sat_pm * IF(ISBLANK(PM_Satisfaction), 0.5, PM_Satisfaction),
  IF(ISBLANK(PM_Satisfaction), 0.5, PM_Satisfaction)
), 0)
```

**Components:**
- Client survey (if available, weighted 80%)
- PM estimation (weighted 20%, or 100% if no survey)

**Weights (default):**
- W_sat_client: 0.8
- W_sat_pm: 0.2

---

### P_flow (Column F)
**Delivery flow & predictability score**

```excel
=ROUND(100 * (
  W_flow_lt * IF(ISBLANK(LeadTime), 0.5, MIN(1, LT_t / MAX(LeadTime, 0.001))) +
  W_flow_fe * IF(ISBLANK(FlowEfficiency), 0.5, MIN(1, FlowEfficiency / FE_t)) +
  W_flow_cr * IF(ISBLANK(CommitmentReliability), 0.5, CommitmentReliability)
), 0)
```

**Components:**
- Lead time (inverted, lower is better)
- Flow efficiency (normalized to target)
- Commitment reliability (direct, higher is better)

**Weights (default):**
- W_flow_lt: 0.4
- W_flow_fe: 0.3
- W_flow_cr: 0.3

---

### P_engineering (Column G)
**Engineering discipline score**

```excel
=ROUND(100 * (
  W_eng_test * IF(ISBLANK(TestMaturity), 0.5, TestMaturity) +
  W_eng_pr * IF(ISBLANK(PR_review_ratio), 0.5, PR_review_ratio) +
  W_eng_arch * IF(ISBLANK(ArchChecklist), 0.5, MIN(1, ArchChecklist / 4))
), 0)
```

**Components:**
- Test maturity (already 0-1)
- PR review ratio (already 0-1)
- Architecture checklist (0-4, normalized to 0-1)

**Weights (default):**
- W_eng_test: 0.5
- W_eng_pr: 0.2
- W_eng_arch: 0.3

---

### P_risk (Column H)
**Risk posture score**

```excel
=ROUND(100 * (
  W_risk_pr * IF(ISBLANK(PRsWithoutReview), 0.5, MAX(0, 1 - PRsWithoutReview / PR_noReview_t)) +
  W_risk_vuln * IF(ISBLANK(HighVuln), 0.5, 
    IF(HighVuln_t = 0, 
      IF(HighVuln = 0, 1, 0),  -- strict: any vuln = 0 score
      MAX(0, 1 - HighVuln / HighVuln_t)
    )
  )
), 0)
```

**Components:**
- PRs without review (inverted, normalized to target)
- High vulnerabilities >30d (inverted, strict mode if target=0)

**Weights (default):**
- W_risk_pr: 0.5
- W_risk_vuln: 0.5

---

## Final Score (Row 10, Column B)

**Weighted aggregate of all dimensions**

```excel
=ROUND(MIN(100,
  W_time * P_time +
  W_cost * P_cost +
  W_quality * P_quality +
  W_value * P_value +
  W_satisfaction * P_satisfaction +
  W_flow * P_flow +
  W_engineering * P_engineering +
  W_risk * P_risk
), 0)
```

**Global Weights (default):**
| Dimension | Weight |
|-----------|--------|
| P_time | 0.12 |
| P_cost | 0.10 |
| P_quality | 0.18 |
| P_value | 0.10 |
| P_satisfaction | 0.12 |
| P_flow | 0.15 |
| P_engineering | 0.18 |
| P_risk | 0.05 |

**Notes:**
- All weights sum to 1
- Score capped at 100
- Each P_* is already 0-100
- No division-by-zero risks (guards everywhere)

---

## Normalization Patterns

### "Higher is better" metrics (direct)
```
normalized = MIN(1, value)
```

### "Lower is better" metrics (inverted)
```
normalized = MIN(1, target / MAX(value, 0.001))
```

### Missing data (neutral)
```
IF(ISBLANK(value), 0.5, ...)
```
