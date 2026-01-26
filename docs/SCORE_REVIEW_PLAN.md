# Score Review Plan

## Overview

This document outlines the plan to review and improve the scoring system. The main objectives are:

1. **Review each score systematically** - validate metrics, exceptions, and calculations
2. **Change neutral value handling** - exclude missing metrics instead of using 0.5
3. **Document all indicators, weights, and targets** - for transparency and tracking

---

## Key Change: Missing Data Handling

### Current Behavior (NEUTRAL_VALUE = 0.5)

When a metric is missing, the system uses 0.5 as a "neutral" value:

```python
# Current approach
score = w1 * value1 + w2 * 0.5 + w3 * value3  # 0.5 is not truly neutral
```

**Problem**: 0.5 is not neutral in many contexts:
- For a metric with target 100%, 0.5 (50%) is a failing score
- For inverted metrics (lower is better), 0.5 can be artificially good or bad

### New Behavior: Exclude and Redistribute

When a metric is missing, exclude it from the calculation and redistribute its weight:

```python
# New approach
available_weights = w1 + w3  # w2 excluded
score = (w1 * value1 + w3 * value3) / available_weights
```

**Benefits**:
- Score reflects only available data
- No artificial impact from missing metrics
- More accurate representation of project health

---

## Scores to Review

### 1. P_time (Schedule Adherence) - Weight: 12% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| SPI | 0.6 | 1.0 | Higher is better | EVM data |
| On-time Milestones | 0.4 | 85% | Higher is better | Milestones list |

**Exceptions**:
- Grace period: 3 days for milestone delivery

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] If SPI missing: score based on milestones only (100% weight)
- [x] If milestones missing: score based on SPI only (100% weight)
- [x] If both missing: returns `None` (no score available)
- [x] 6 tests covering all scenarios

**Files Modified**:
- `backend/app/services/calculators/base.py` - Added `WeightedComponent`, `_weighted_average`
- `backend/app/services/calculators/dimensions.py` - Refactored `TimeCalculator`
- `backend/tests/test_calculators.py` - Updated and added tests

---

### 2. P_cost (Budget Adherence) - Weight: 10% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| CPI | 0.7 | 1.0 | Higher is better | EVM data |
| Budget Variance | 0.3 | 0% overrun | Lower is better | EVM data |

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] CPI: `min(1, cpi / target)`
- [x] Variance: `max(0, 1 - overrun%)` where overrun = (actual - budget) / budget
- [x] If CPI missing: score based on variance only (100% weight)
- [x] If variance missing: score based on CPI only (100% weight)
- [x] If both missing: returns `None`
- [x] 6 tests covering all scenarios

---

### 3. P_quality (Product Quality) - Weight: 18% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| Defect Density | 0.05 | 3% | Lower is better | Jira defects |
| Escaped Rate | 0.15 | 1% | Lower is better | Jira defects |
| MTTR | 0.05 | 24h | Lower is better | Jira defects |
| Story Review | 0.25 | 100% | Higher is better | Flow metrics |
| Governance | 0.20 | 100% | Higher is better | Manual input |
| PR Review | 0.10 | 100% | Higher is better | GitHub metrics |
| Change Failure Rate | 0.15 | 15% | Lower is better | GitHub metrics |
| Post-contract Tasks | 0.05 | 3 | Lower is better | Jira defects |

**Exceptions**:
- **Sev1 Incident Cap**: If `sev1_incident=true`, max score is 60 points

**Implementation**:
- [x] Uses `WeightedComponent` pattern for all 8 components
- [x] Missing components excluded and weights redistributed
- [x] Sev1 cap applied AFTER weighted average (respects None)
- [x] If all components missing: returns `None`
- [x] 7 tests covering all scenarios including Sev1 cap

---

### 4. P_value (Strategic Value) - Weight: 10% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| OKR Impact | 1.0 | N/A | Categorical | Manual input (end-of-project) |

**Categorical Mapping**:
| Impact Level | Score |
|--------------|-------|
| Low | 25 |
| Medium | 55 |
| High | 80 |
| Transformational | 100 |

**Implementation**:
- [x] Direct mapping from categorical to score
- [x] If okr_impact is None: returns `None`
- [x] 5 tests covering all impact levels + no data

---

### 5. P_satisfaction (Client Satisfaction) - Weight: 12% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| Client Survey | 0.9 | 100% | Higher is better | Survey data |
| PM Estimation | 0.1 | 90% | Higher is better | Manual input |

**Special Logic**:
- If no client survey: PM estimation = 100% weight (development phase)
- If both available: 90% client + 10% PM (end of project)

**Client Survey Questions** (8 questions, 1-5 scale):

| Question | Weight |
|----------|--------|
| Understanding | 0.12 |
| Proactivity | 0.12 |
| Communication | 0.10 |
| Delivery Time | 0.14 |
| Response Time | 0.10 |
| Quality | 0.24 |
| Expectations | 0.12 |
| Recommend | 0.06 |

**PM Estimation Components**:
- Delivery Complaints: No=1.0, Yes=0.4 (weight: 30%)
- Design Complaints: No=1.0, Yes=0.4 (weight: 30%)
- Overall Estimation: 1-5 scale / 5 (weight: 40%)

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] If client survey missing: PM estimation = 100% weight
- [x] If PM estimation missing: Client survey = 100% weight
- [x] If both missing: returns `None`
- [x] 5 tests covering all scenarios

---

### 6. P_flow (Flow & Predictability) - Weight: 15% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| Lead Time | 0.35 | 3 days | Lower is better | Flow metrics |
| Commitment Reliability | 0.25 | 100% | Higher is better | Flow metrics |
| PR Size | 0.15 | 400 lines | Lower is better | GitHub metrics |
| Review Turnaround | 0.10 | 24h | Lower is better | GitHub metrics |
| Deployment Frequency | 0.15 | 1/day | Higher is better | GitHub metrics |

**Exceptions**:
- None

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] All 5 components use normalize_to_target (lower/higher is better)
- [x] Missing components excluded and weights redistributed
- [x] If all components missing: returns `None`
- [x] 5 tests covering all scenarios

---

### 7. P_engineering (Engineering Maturity) - Weight: 18% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| Test Maturity | 0.5 | 60% | Higher is better | Manual input |
| PR Review Ratio | 0.2 | 100% | Higher is better | GitHub metrics |
| Architecture | 0.3 | 100% | Higher is better | Manual input |

**Test Maturity Components** (5 areas, 1-5 scale):

| Area | Weight |
|------|--------|
| E2E Tests | 0.4 |
| Unit Tests | 0.1 |
| Accessibility Tests | 0.1 |
| Security Tests | 0.2 |
| Frontend Tests | 0.2 |

**Architecture Checklist** (4 items, boolean):
1. Documentation up to date
2. IaC implemented
3. ADRs maintained
4. Diagrams updated

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] All 3 components already normalized to 0-1 scale
- [x] Missing components excluded and weights redistributed
- [x] If all components missing: returns `None`
- [x] 5 tests covering all scenarios

---

### 8. P_risk (Risk Posture) - Weight: 5% ✅ COMPLETED

| Indicator | Weight | Target | Type | Source |
|-----------|--------|--------|------|--------|
| PRs without Review | 0.5 | 2% | Lower is better | GitHub metrics |
| High Vulnerabilities | 0.5 | 0 | Strict zero | GitHub metrics |

**Special Logic**:
- High Vulns: Strict zero tolerance (target=0, any value>0 = score 0)
- PRs without Review: Calculated as percentage of total PRs

**Implementation**:
- [x] Uses `WeightedComponent` pattern for weight redistribution
- [x] PR ratio calculated using total_prs parameter
- [x] Strict zero mode for vulnerabilities (any value > 0 = score 0)
- [x] Missing components excluded and weights redistributed
- [x] If all components missing: returns `None`
- [x] 6 tests covering all scenarios

---

## Implementation Plan

### Phase 1: Documentation & Analysis
1. Create this plan document ✓
2. Document current behavior for each score
3. Identify all places where NEUTRAL_VALUE is used
4. Design test cases for new behavior

### Phase 2: Core Change - Redistribute Weights
1. Modify `BaseCalculator` to support weight redistribution
2. Update `_safe_value` method to track missing components
3. Implement new calculation pattern in each calculator
4. Add unit tests for new behavior

### Phase 3: Review Each Score
For each of the 8 scores:
1. Review calculation logic
2. Validate exceptions and special rules
3. Apply weight redistribution pattern
4. Update/add unit tests
5. Document final behavior

### Phase 4: Integration & Testing
1. Run full test suite
2. Test with real project data
3. Compare old vs new scores
4. Document any significant changes

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/services/normalizers/base.py` | Keep NEUTRAL_VALUE for reference but change usage |
| `backend/app/services/calculators/base.py` | Add weight redistribution helpers |
| `backend/app/services/calculators/dimensions.py` | Update all 8 calculators |
| `backend/tests/test_calculators.py` | Add tests for missing data behavior |
| `docs/SCORE_REVIEW_PLAN.md` | This document - track progress |

---

## Review Order

We will review in order of impact (highest weight first):

1. **P_quality** (18%) - Most complex, 8 components
2. **P_engineering** (18%) - 3 components + sub-components
3. **P_flow** (15%) - 5 components, DORA metrics
4. **P_satisfaction** (12%) - 2 components + survey
5. **P_time** (12%) - 2 components
6. **P_cost** (10%) - 2 components
7. **P_value** (10%) - 1 component, categorical
8. **P_risk** (5%) - 2 components, strict zero logic

---

## Progress Tracking

| Score | Review | Refactor | Tests | Docs |
|-------|--------|----------|-------|------|
| P_time | ✅ | ✅ | ✅ | ✅ |
| P_cost | ✅ | ✅ | ✅ | ✅ |
| P_quality | ✅ | ✅ | ✅ | ✅ |
| P_value | ✅ | ✅ | ✅ | ✅ |
| P_satisfaction | ✅ | ✅ | ✅ | ✅ |
| P_flow | ✅ | ✅ | ✅ | ✅ |
| P_engineering | ✅ | ✅ | ✅ | ✅ |
| P_risk | ✅ | ✅ | ✅ | ✅ |

Legend: ⬜ Pending | 🔄 In Progress | ✅ Complete

**ALL SCORES REVIEWED AND REFACTORED** ✅

Total tests: 49 calculator tests
- TimeCalculator: 6 tests
- CostCalculator: 6 tests
- QualityCalculator: 7 tests
- ValueCalculator: 5 tests
- SatisfactionCalculator: 5 tests
- FlowCalculator: 5 tests
- EngineeringCalculator: 5 tests
- RiskCalculator: 6 tests
- FinalScoreCalculator: 4 tests
