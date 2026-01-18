# Design Principles & Decisions

## Core Philosophy

The Project Scorecard is designed to be:
- **Evidence-based**: No subjective scores, all metrics traceable
- **Normalized**: Everything resolves to 0-100 for comparability
- **Composable**: Dimensions evolve independently
- **Audit-friendly**: Weights and formulas are explicit
- **Bias-resistant**: Neutral defaults only when data genuinely unavailable

---

## Key Design Decisions

### 1. Scripts vs Formulas Separation

**Decision**: Scripts ONLY collect data. All scoring logic lives in formulas.

**Rationale**:
- Easier to audit (formulas visible in spreadsheet)
- Non-technical stakeholders can verify logic
- Changes don't require code deployment
- Clear separation of concerns

**Migration implication**: Keep this separation. Collectors write raw data, calculators compute scores.

---

### 2. Risk Separated from Quality

**Decision**: P_risk and P_quality are distinct dimensions.

**Rationale**:
- Quality = outcomes (defects found, escaped bugs)
- Risk = posture (governance practices, security debt)
- A project can have good quality but high risk (luck vs discipline)
- A project can have low risk but mediocre quality (careful but slow)

---

### 3. Satisfaction Separated from Value

**Decision**: P_satisfaction and P_value are distinct dimensions.

**Rationale**:
- Satisfaction = client perception (survey, complaints)
- Value = business impact (OKR contribution)
- A client can be satisfied with low-value work
- High-value work can have unsatisfied clients (hard projects)

---

### 4. Flow ≠ Speed

**Decision**: Flow efficiency measures waste, not raw velocity.

**Rationale**:
- Lead time = how fast (To Do → Done)
- Flow efficiency = how much waste (active time / total time)
- Fast but wasteful ≠ good
- Slow but efficient might be acceptable

Both are tracked, weighted separately.

---

### 5. Neutral Defaults (0.5)

**Decision**: Use 0.5 (neutral) only when data is genuinely not yet available.

**When to use neutral**:
- Metric not applicable yet (project just started)
- Data collection pending (survey not sent)

**When NOT to use neutral**:
- Data exists but is bad → penalize
- Governance tool disabled → penalize
- Survey sent and answered → never neutral

**Rationale**:
- Avoids inflating early-phase projects
- Avoids masking governance gaps
- Avoids penalizing absence unfairly

---

### 6. ROI Removed from P_value

**Decision**: ROI was deliberately removed.

**Rationale**:
- CPI already captures cost efficiency
- SPI already captures schedule efficiency
- ROI would double-count these factors
- OKR impact is a cleaner strategic signal

---

### 7. Inverted Metrics Pattern

**Decision**: "Lower is better" metrics use inverted normalization.

```
normalized = MIN(1, target / MAX(value, 0.001))
```

**Applied to**:
- Defect density (fewer is better)
- Escaped rate (fewer is better)
- MTTR (shorter is better)
- Lead time (shorter is better)
- PRs without review (fewer is better)
- High vulnerabilities (fewer is better)

**Rationale**:
- All normalized scores are 0-1 where higher is better
- Allows consistent weighting and aggregation
- `MAX(value, 0.001)` prevents division by zero

---

### 8. Strict Mode for Critical Targets

**Decision**: When target = 0, any deviation = 0 score.

**Example**: HighVuln_t = 0 (zero tolerance for high vulns >30d)
```
IF target = 0:
    IF value = 0: score = 1
    ELSE: score = 0  # strict penalty
```

**Rationale**:
- Some metrics have non-negotiable targets
- Security vulnerabilities >30 days = unacceptable
- Allows governance to enforce hard limits

---

### 9. Weight Validation

**Decision**: All weight groups must sum to exactly 1.

**Implementation**: Validator cells in Params sheet.

**Rationale**:
- Prevents configuration errors
- Ensures scores are properly normalized
- Makes weight changes explicit (must adjust others)

---

### 10. Grace Period for Milestones

**Decision**: GraceDays constant allows flexibility.

**Implementation**:
```
on_time = actual_date <= planned_date + GraceDays
```

**Default**: 3 days

**Rationale**:
- Minor delays shouldn't penalize unfairly
- Configurable per organization
- Recognizes real-world delivery flexibility

---

### 11. Sev1 Cap

**Decision**: Critical production incidents cap quality score.

**Implementation**:
```
IF Sev1_in_prod = 1:
    P_quality = MIN(P_quality, Sev1_cap)
```

**Default**: Sev1_cap = 60

**Rationale**:
- Major incidents should have significant impact
- Other quality metrics shouldn't mask critical failures
- Configurable severity of penalty

---

## Anti-Patterns Avoided

### NOT a velocity scoreboard
- Doesn't reward shipping fast regardless of quality
- Flow efficiency > raw speed

### NOT a people performance metric
- Measures project health, not individual performance
- Teams should use for improvement, not punishment

### NOT subjective opinion disguised as math
- All inputs are traceable
- No "gut feel" scores

### NOT fragile to tooling changes
- Graceful degradation when data missing
- Neutral defaults prevent crashes
