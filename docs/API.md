# Project Scorecard API Documentation

Base URL: `http://localhost:8000/api`

## Authentication

Currently, the API does not require authentication. Authentication will be added in a future release.

---

## Projects

### List Projects

```http
GET /projects
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Project Alpha",
    "jira_project_key": "ALPHA",
    "github_repo": "org/alpha",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Project

```http
POST /projects
Content-Type: application/json

{
  "name": "Project Alpha",
  "jira_project_key": "ALPHA",
  "github_repo": "org/alpha"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "Project Alpha",
  "jira_project_key": "ALPHA",
  "github_repo": "org/alpha",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Get Project

```http
GET /projects/{project_id}
```

### Update Project

```http
PATCH /projects/{project_id}
Content-Type: application/json

{
  "name": "Project Alpha Updated"
}
```

### Delete Project

```http
DELETE /projects/{project_id}
```

**Response:** `204 No Content`

---

## Metrics

### Create Metrics

```http
POST /metrics/project/{project_id}
Content-Type: application/json

{
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "evm_data": {
    "budget_total": 100000,
    "cost_to_date": 45000,
    "percent_completed": 0.5,
    "percent_planned": 0.5
  },
  "milestones": [
    {
      "name": "Phase 1",
      "planned_date": "2024-01-15",
      "actual_date": "2024-01-14",
      "criticality_weight": 1.0
    }
  ],
  "jira_defects": {
    "bugs_closed": 10,
    "tasks_completed": 100,
    "escaped_defects": 1,
    "mttr_hours": 4.5,
    "incidents_count": 2
  },
  "flow_metrics": {
    "lead_time_days": 2.5,
    "lead_time_sample_size": 150,
    "commitment_reliability": 0.9,
    "committed_issues": 330,
    "single_sprint_issues": 107,
    "multi_sprint_issues": 223,
    "total_stories": 50,
    "stories_with_reviewer": 48
  },
  "github_metrics": {
    "prs_without_review": 2,
    "total_merged_prs": 75,
    "pr_review_ratio": 0.97,
    "high_severity_vulns": 0
  },
  "test_maturity": {
    "e2e": 4,
    "unit": 5,
    "accessibility": 3,
    "security": 4,
    "frontend": 4
  },
  "architecture": {
    "docs_up_to_date": true,
    "iac_implemented": true,
    "adrs_maintained": true,
    "diagrams_updated": false
  },
  "pm_satisfaction": {
    "delivery_complaints": "no",
    "design_complaints": "no",
    "overall_estimation": 4
  },
  "client_survey": {
    "understanding": 5,
    "proactivity": 4,
    "communication": 5,
    "delivery_time": 4,
    "response_time": 5,
    "quality": 5,
    "expectations": 4,
    "recommend": 5
  },
  "strategic_impact": "high",
  "governance_exceptions": 0,
  "sev1_incident": false
}
```

### Get Latest Metrics

```http
GET /metrics/project/{project_id}/latest
```

### List Project Metrics

```http
GET /metrics/project/{project_id}
```

---

## Scores

### Calculate Scores (Ad-hoc)

Calculate scores without storing metrics. Useful for simulations.

```http
POST /scores/calculate
Content-Type: application/json

{
  "metrics": { ... },  // Same as MetricsCreate
  "sev1_incident": false
}
```

**Response:**
```json
{
  "indicators": {
    "spi": 1.0,
    "on_time_milestones": 1.0,
    "cpi": 1.11,
    "budget_variance": 0,
    "defect_density": 10.0,
    "escaped_rate": 1.0,
    "mttr_hours": 4.5,
    "governance_compliance": 1.0,
    "lead_time_days": 2.5,
    "lead_time_sample_size": 150,
    "commitment_reliability": 0.9,
    "pr_review_ratio": 0.97,
    "prs_without_review": 2,
    "high_vulns": 0,
    "test_maturity": 0.82,
    "arch_checklist": 0.75,
    "story_review_ratio": 0.96,
    "okr_impact": 0.8,
    "pm_satisfaction": 0.88,
    "client_satisfaction": 0.92
  },
  "scores": {
    "score": 85,
    "dimensions": {
      "p_time": 100,
      "p_cost": 100,
      "p_quality": 78,
      "p_value": 80,
      "p_satisfaction": 90,
      "p_flow": 85,
      "p_engineering": 84,
      "p_risk": 50
    },
    "weights_applied": {
      "time": 0.12,
      "cost": 0.10,
      "quality": 0.18,
      "value": 0.10,
      "satisfaction": 0.12,
      "flow": 0.15,
      "engineering": 0.18,
      "risk": 0.05
    }
  }
}
```

### Get Project Scores

Calculate scores from the project's latest metrics.

```http
GET /scores/project/{project_id}
```

### Get Score History

```http
GET /scores/project/{project_id}/history?limit=10
```

---

## Configuration

### Get Scoring Configuration

```http
GET /config
```

**Response:**
```json
{
  "targets": {
    "defect_density": 3,
    "escaped_rate": 0.01,
    "mttr_hours": 24,
    "spi": 1,
    "cpi": 1,
    "lead_time_days": 5,
    "high_vuln_count": 0,
    "gov_exceptions": 2,
    "pr_no_review_ratio": 0.02
  },
  "global_weights": {
    "time": 0.12,
    "cost": 0.10,
    "quality": 0.18,
    "value": 0.10,
    "satisfaction": 0.12,
    "flow": 0.15,
    "engineering": 0.18,
    "risk": 0.05
  },
  "constants": {
    "sev1_cap": 60,
    "grace_days": 3
  },
  "weight_validation": {
    "global": true,
    "time": true,
    "cost": true,
    "quality": true,
    "value": true,
    "satisfaction": true,
    "flow": true,
    "engineering": true,
    "risk": true
  }
}
```

### Validate Configuration

```http
GET /config/validate
```

**Response:**
```json
{
  "valid": true,
  "groups": {
    "global": true,
    "time": true,
    "cost": true,
    "quality": true,
    "value": true,
    "satisfaction": true,
    "flow": true,
    "engineering": true,
    "risk": true
  }
}
```

---

## Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

## Error Responses

### 404 Not Found

```json
{
  "detail": "Project not found: uuid"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error

```json
{
  "detail": "Configuration error: ..."
}
```

---

## Rate Limiting

Currently no rate limiting is implemented. This will be added in a future release.

---

## Versioning

The API is currently at version 1.0.0. Future versions may include breaking changes under new path prefixes (e.g., `/api/v2`).
