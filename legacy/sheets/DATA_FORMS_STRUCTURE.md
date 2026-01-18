# Data_Forms Structure

Esta hoja contiene todos los inputs crudos del sistema, tanto manuales como automatizados desde Jira/GitHub.

## Secciones

### 1. Project Identification (Rows 1-3)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 1 | Project Name | string | Manual |
| 2 | Jira ID | string | Manual |
| 3 | Github Repo | string | Manual (format: `org/repo`) |

### 2. EVM Inputs & Calculations (Rows 5-20)
Earned Value Management para P_time y P_cost.

| Row | Field | Type | Source | Notes |
|-----|-------|------|--------|-------|
| 8 | Budget (PV total) | number | Manual | Planned Value total |
| 9 | Cost to date (AC) | number | Manual | Actual Cost |
| 10 | % Completed (EV ratio 0..1) | decimal | Manual | 0-1, estimation of completion |
| 11 | % Planned to date (0..1) | decimal | Manual | Planned progress |
| 13 | EV | number | **Formula** | `=B8*B10` |
| 14 | CPI | number | **Formula** | `=IF(B9>0,B13/B9,NA())` |
| 15 | SPI | number | **Formula** | `=IF(B11>0,B10/B11,NA())` |

### 3. On-Time Milestones (Rows 22-42)
Weighted milestone tracking para P_time.

| Row | Field | Type | Notes |
|-----|-------|------|-------|
| 24 | OnTimeMilestones_0to1 | decimal | **Formula** - weighted result |
| 25+ | Milestone table | - | Columns: Milestone, PlannedDate, ActualDate, CriticalityWeight |

**Milestone Table Columns:**
- A: Milestone name
- B: PlannedDate (date)
- C: ActualDate (date, optional)
- D: CriticalityWeight (number, default 1)
- E: DueFlag (formula: 1 if due)
- F: OnTimeFlag (formula: 1 if on time)
- G: WeightUsed (formula)
- H: WeightedOnTime (formula)

**Key Formula:**
```excel
OnTimeMilestones_0to1 = SUM(H26:H37) / SUM(G26:G37)
```

### 4. Defect Density (Rows 45-54)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 47 | # Bugs closed | integer | Jira API |
| 48 | # Tasks completed | integer | Jira API |
| 49 | DefectDensity_per_100Tasks | decimal | **Formula**: `(bugs/tasks)*100` |

### 5. Escaped Defects (Rows 56-64)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 58 | EscapedRate_per_100Tasks | decimal | Jira API |
| 59 | # Escaped defects | integer | Jira API (bugs in Staging/Production) |

### 6. MTTR (Rows 66-74)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 68 | MTTR_hours | decimal | Jira API |
| 69 | # Incidents | integer | Jira API |

### 7. Governance Compliance (Rows 76-83)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 78 | Number of exceptions | integer | Manual (peer review) |

### 8. PM Client Satisfaction Estimation (Rows 85-94)
| Row | Field | Type | Options |
|-----|-------|------|---------|
| 87 | Delivery complaints? | string | "yes" / "no" / "-" |
| 88 | Design complaints? | string | "yes" / "no" / "-" |
| 89 | Overall estimation 1-5 | integer | 1-5 |

### 9. Automated Test Maturity (Rows 96-107)
| Row | Field | Type | Scale |
|-----|-------|------|-------|
| 98 | End2End tests | integer | 0-5 |
| 99 | Unit Tests | integer | 0-5 |
| 100 | Accessibility tests | integer | 0-5 |
| 101 | Security tests | integer | 0-5 |
| 102 | Front end tests | integer | 0-5 |

### 10. Flow Metrics (Rows 109-134)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 111 | Lead Time (days) | decimal | Jira API |
| 120 | Flow Efficiency 0-1 | decimal | Jira API |
| 129 | Commitment Reliability | decimal | Jira API |

### 11. GitHub PR Metrics (Rows 136-163)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 138 | PRs without review | integer | GitHub API |
| 139 | Total merged | integer | GitHub API |
| 148 | PR review ratio | decimal | GitHub API |
| 158 | High severity vulnerabilities | integer | GitHub Dependabot API |

### 12. Architecture Checklist (Rows 165-175)
| Row | Field | Type | Options |
|-----|-------|------|---------|
| 167 | Architecture docs up to date | integer | 0 or 1 |
| 168 | IaC implemented | integer | 0 or 1 |
| 169 | ADRs maintained | integer | 0 or 1 |
| 170 | Diagrams updated | integer | 0 or 1 |

### 13. Story Review Ratio (Rows 177-185)
| Row | Field | Type | Source |
|-----|-------|------|--------|
| 179 | Total user stories | integer | Jira API |
| 180 | Stories with reviewer | integer | Jira API |

### 14. End of Project Indicators (Rows 187-209)

#### Strategic Impact (Row 190)
Dropdown options:
- "Low impact: Minor improvement to existing system"
- "Medium impact: Supports one team or process improvement"  
- "High impact: Enables new capability or significant efficiency"
- "Transformational: Strategic enabler for organization"

#### Client Satisfaction Survey (Rows 199-206)
| Row | Field | Scale |
|-----|-------|-------|
| 199 | Understanding your needs | 1-5 |
| 200 | Proactivity | 1-5 |
| 201 | Communication | 1-5 |
| 202 | Overall time of delivery | 1-5 |
| 203 | Response time | 1-5 |
| 204 | Quality of deliverables | 1-5 |
| 205 | Met expectations | 1-5 |
| 206 | Likely to recommend | 1-5 |
