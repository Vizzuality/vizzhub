# Project Scorecard - Legacy Documentation

This folder contains the complete documentation of the Google Sheets + Google Apps Script implementation of the Project Scorecard system.

## System Overview

The Project Scorecard evaluates software development projects across **8 dimensions**:

| Dimension | Code | Focus |
|-----------|------|-------|
| Delivery Timeliness | P_time | Schedule adherence |
| Cost Control | P_cost | Budget discipline |
| Product Quality | P_quality | Defects, governance |
| Strategic Value | P_value | OKR impact |
| Client Satisfaction | P_satisfaction | Survey + PM estimation |
| Flow & Predictability | P_flow | Lead time, efficiency |
| Engineering Maturity | P_engineering | Testing, reviews, architecture |
| Risk Posture | P_risk | Security, code review |

## Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│   Data_Forms    │────▶│      Data       │
│  Jira, GitHub   │     │   (raw inputs)  │     │  (normalized)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌─────────────────┐             │
                        │     Params      │─────────────┤
                        │ (weights/targets)│            │
                        └─────────────────┘             ▼
                                                ┌─────────────────┐
                                                │     Scores      │
                                                │ (0-100 scores)  │
                                                └─────────────────┘
```

## Folder Structure

```
legacy/
├── README.md                 # This file
├── sheets/
│   ├── DATA_FORMS_STRUCTURE.md   # Input fields documentation
│   ├── PARAMS_STRUCTURE.md       # Configuration documentation
│   ├── DATA_STRUCTURE.md         # Normalized indicators
│   └── SCORES_STRUCTURE.md       # Score calculations
├── formulas/
│   └── ALL_FORMULAS.md           # Complete formula reference
├── docs/
│   └── DESIGN_PRINCIPLES.md      # System design decisions
└── original/
    └── Project_Scorecard_v3.xlsx # Original spreadsheet
```

## Key Design Principles

1. **Scripts only collect data** → formulas decide meaning
2. **All ratios normalized** before weighting (0-1 scale)
3. **Risk ≠ Quality** → separated intentionally
4. **Satisfaction ≠ Value** → different dimensions
5. **Flow ≠ Speed** → efficiency vs. raw velocity
6. **Neutral defaults (0.5)** only when data genuinely unavailable
7. **Penalize** when governance tools are disabled

## Data Sources

### Jira API
- Defect counts, task counts
- Lead time, flow efficiency
- Commitment reliability
- MTTR (incidents)
- Story review status

### GitHub API
- PR review ratios
- PRs without review count
- Total merged PRs

### GitHub Dependabot
- High severity vulnerabilities >30 days

### Manual Inputs
- EVM data (budget, costs, completion %)
- Milestones (planned/actual dates)
- Architecture checklist
- Test maturity ratings
- PM satisfaction estimation
- Client survey responses
- Strategic impact selection

## Normalization Patterns

### "Higher is better" (direct)
```python
normalized = min(1, value)
```

### "Lower is better" (inverted)
```python
normalized = min(1, target / max(value, 0.001))
```

### Missing data (neutral)
```python
if value is None:
    return 0.5  # neutral
```

### Disabled governance tool
```python
if tool_disabled:
    return 0  # worst case penalty
```

## Migration Notes

When migrating to FastAPI + React:

1. **Params sheet** → `scoring_config` table with JSON
2. **Data_Forms** → `raw_metrics` table per project
3. **Data** → computed on-the-fly by normalizer services
4. **Scores** → computed on-the-fly by calculator services
5. **Named ranges** → config dictionary in Python
6. **Excel formulas** → Python functions in calculators/

## Files to Review

For migration, review in this order:
1. `sheets/PARAMS_STRUCTURE.md` → understand configuration
2. `sheets/DATA_FORMS_STRUCTURE.md` → understand inputs
3. `formulas/ALL_FORMULAS.md` → understand calculations
4. `sheets/SCORES_STRUCTURE.md` → understand final scoring
