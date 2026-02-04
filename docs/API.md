# Project Scorecard API Documentation

Base URL: `http://localhost:8000/api`

## Authentication

All endpoints require JWT authentication (except `/health` and OAuth callbacks).

**Development mode** (`DEBUG=true`): Authentication is bypassed.

**Headers:**
```http
Authorization: Bearer <jwt_token>
```

Generate test tokens:
```bash
cd backend
python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
```

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
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "status": "in_progress",
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
  "github_repo": "org/alpha",
  "start_date": "2024-01-01",
  "end_date": "2024-06-30"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "Project Alpha",
  "jira_project_key": "ALPHA",
  "github_repo": "org/alpha",
  "start_date": "2024-01-01",
  "end_date": "2024-06-30",
  "status": "in_progress",
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

## Metrics Capture

### Capture Period (Recommended)

Capture metrics from Jira and GitHub for a specific month. **Creates BOTH punctual and cumulative snapshots.**

```http
POST /projects/{project_id}/capture-period
Content-Type: application/json

{
  "year": 2024,       // Optional - defaults to current year
  "month": 6,         // Optional - defaults to current month
  "force": false      // Optional - overwrite existing if true
}
```

**When `year`/`month` are omitted**:
- Defaults to current month
- Uses `today` as end date (not last day of month)
- Cumulative: `project.start_date` → `today`
- Punctual: 1st of current month → `today`

**Typical request** (from UI "Collect Metrics" button for selected period):
```http
POST /projects/{project_id}/capture-period
Content-Type: application/json

{"year": 2024, "month": 6, "force": true}
```

**Response:** `201 Created`
```json
{
  "punctual": {
    "id": "uuid",
    "project_id": "uuid",
    "period_year": 2024,
    "period_month": 6,
    "snapshot_type": "punctual",
    "indicators": { ... },
    "scores": { ... }
  },
  "cumulative": {
    "id": "uuid",
    "project_id": "uuid",
    "period_year": 2024,
    "period_month": 6,
    "snapshot_type": "cumulative",
    "indicators": { ... },
    "scores": { ... }
  }
}
```

**Error:** `409 Conflict` if period already captured (use `force: true` to overwrite)

### Capture History (Batch - Async)

> **Note:** Use `POST /jobs/capture-history` instead. Batch capture now runs as a background job for better reliability and progress tracking. See [Background Jobs](#background-jobs) section.

### Collect Jira Metrics Only (Legacy)

> ⚠️ **Deprecated**: Use `POST /projects/{id}/capture-period` instead. It collects both Jira and GitHub and creates both snapshot types automatically.

```http
POST /collect/project/{project_id}/jira
```

### Collect GitHub Metrics Only (Legacy)

> ⚠️ **Deprecated**: Use `POST /projects/{id}/capture-period` instead.

```http
POST /collect/project/{project_id}/github
```

---

## Background Jobs

Long-running batch operations (historical capture) run asynchronously via ARQ + Redis.

### Create Batch Historical Capture Job

```http
POST /jobs/capture-history
Content-Type: application/json

{
  "project_id": "uuid",
  "from_year": 2024,
  "from_month": 1,
  "to_year": 2024,
  "to_month": 12,
  "force": true
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "type": "capture_history",
  "name": "Historical Capture: Project Alpha",
  "description": "January 2024 - December 2024 (12 months)",
  "status": "pending",
  "progress": 0,
  "progress_message": null,
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Get Job Status (Polling)

Poll this endpoint to track job progress.

```http
GET /jobs/{job_id}
```

**Response:**
```json
{
  "id": "uuid",
  "type": "capture_history",
  "name": "Historical Capture: Project Alpha",
  "description": "January 2024 - December 2024 (12 months)",
  "status": "running",
  "progress": 42,
  "progress_message": "Processing May 2024...",
  "logs": "[10:00:01] OK: January 2024\n[10:00:06] OK: February 2024...",
  "result": null,
  "error_message": null,
  "created_at": "2024-01-15T10:00:00Z",
  "started_at": "2024-01-15T10:00:01Z",
  "completed_at": null
}
```

**Job statuses:** `pending` → `running` → `completed` | `failed` | `cancelled`

### List Jobs

```http
GET /jobs?project_id=uuid&status=running&type=capture_history&limit=20
```

All parameters optional. Returns list of `JobSummaryResponse`.

### Cancel Pending Job

```http
POST /jobs/{job_id}/cancel
```

Only works for `pending` jobs. Returns `400` if job is already running.

### Retry Failed Job

```http
POST /jobs/{job_id}/retry
```

Creates a new job with the same parameters. Only works for `failed` jobs.

---

## Snapshot Types

All metrics endpoints support filtering by snapshot type:

| Type | Description | Date Range |
|------|-------------|------------|
| `cumulative` | Project-to-date (default) | `project.start_date` → `period_end` |
| `punctual` | Single month only | First day of month → Last day of month |

**Query parameter:** `?snapshot_type=cumulative` or `?snapshot_type=punctual`

---

## Metrics

### Create/Update Metrics

Uses upsert behavior: if metrics exist for the same `(project, year, month, snapshot_type)`, they are updated.

```http
POST /metrics/project/{project_id}
Content-Type: application/json

{
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "snapshot_type": "cumulative",  // optional, defaults to "cumulative"
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
    "high_severity_vulns": 0,
    "high_severity_vulns_total": 0,
    "pr_size_median": 150,
    "review_turnaround_hours": 4.5,
    "deployment_frequency": 0.5,
    "release_count_90d": 3,
    "change_failure_rate": 0.1,
    "total_releases": 10,
    "failed_releases": 1
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

### List Project Metrics

```http
GET /metrics/project/{project_id}
GET /metrics/project/{project_id}?snapshot_type=cumulative   # default
GET /metrics/project/{project_id}?snapshot_type=punctual     # single month only
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
    "commitment_reliability": 0.9,
    "pr_review_ratio": 0.97,
    "prs_without_review": 2,
    "high_vulns": 0,
    "test_maturity": 0.82,
    "arch_checklist": 0.75,
    "story_review_ratio": 0.96,
    "okr_impact": 0.8,
    "pm_satisfaction": 0.88,
    "client_satisfaction": 0.92,
    "pr_size_median": 150,
    "review_turnaround_hours": 4.5,
    "deployment_frequency": 0.5,
    "change_failure_rate": 0.1,
    "post_contract_tasks": 0
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
GET /scores/project/{project_id}?snapshot_type=cumulative   # default
GET /scores/project/{project_id}?snapshot_type=punctual     # single month
```

### Get Score History

```http
GET /scores/project/{project_id}/history?limit=10
GET /scores/project/{project_id}/history?limit=10&snapshot_type=cumulative
```

### Get Metrics History

```http
GET /metrics/project/{project_id}/history?limit=12
GET /metrics/project/{project_id}/history?limit=12&snapshot_type=cumulative
```

**Response:**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "period_year": 2024,
    "period_month": 6,
    "snapshot_type": "cumulative",
    "weights_applied": { ... },
    "targets_applied": { ... },
    "created_at": "2024-06-30T12:00:00Z",
    "indicators": { ... },
    "scores": { ... }
  }
]
```

### Get Metrics by Period

```http
GET /metrics/project/{project_id}/{year}/{month}
GET /metrics/project/{project_id}/2024/6?snapshot_type=cumulative
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
    "spi": 0.8,
    "cpi": 0.8,
    "lead_time_days": 5,
    "high_vuln_count": 0,
    "gov_exceptions": 2,
    "pr_no_review_ratio": 0.02,
    "story_review_ratio": 0.9,
    "commitment_reliability": 0.8,
    "test_maturity": 0.7,
    "architecture": 0.75,
    "pm_satisfaction": 0.85,
    "client_satisfaction": 0.8
  },
  "ideals": {
    "spi": 1.0,
    "cpi": 1.0
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
    "Global Weights": true,
    "Time Weights": true,
    "Cost Weights": true,
    "Quality Weights": true,
    "Value Weights": true,
    "Satisfaction Weights": true,
    "Flow Weights": true,
    "Engineering Weights": true,
    "Risk Weights": true
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

## Slack Administration

### Get Slack Configuration

```http
GET /admin/slack/config
```

**Response:**
```json
{
  "id": 1,
  "bot_token_configured": true,
  "leadership_channel_id": "C1234567890",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Update Slack Configuration

```http
PUT /admin/slack/config
Content-Type: application/json

{
  "bot_token": "xoxb-your-bot-token",
  "leadership_channel_id": "C1234567890"
}
```

### Test Slack Connection

```http
POST /admin/slack/test
```

**Response:**
```json
{
  "ok": true,
  "team": "YourWorkspace",
  "bot_id": "B1234567890",
  "error": null
}
```

### List Slack Channels

```http
GET /admin/slack/channels
```

**Response:**
```json
[
  {
    "id": "C1234567890",
    "name": "general",
    "is_private": false
  }
]
```

---

## Alert Definitions

### List Alert Definitions

```http
GET /admin/alerts/
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "budget_exceeded",
    "description": "Project budget has been fully consumed",
    "category": "business",
    "channel_type": "leadership",
    "schedule": "daily_check_monthly_report",
    "is_enabled": true,
    "config_json": {},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Update Alert Definition

```http
PUT /admin/alerts/{alert_id}
Content-Type: application/json

{
  "is_enabled": false,
  "config_json": {"grace_days": 45}
}
```

### Get Alert Templates

```http
GET /admin/alerts/{alert_id}/templates
```

### Send Test Alert

```http
POST /admin/alerts/{alert_id}/test
Content-Type: application/json

{
  "project_id": "uuid"
}
```

---

## Message Templates

### Update Message Template

```http
PUT /admin/templates/{template_id}
Content-Type: application/json

{
  "message_template": ":warning: *{project_name}* budget alert: {budget_percent}%",
  "is_active": true
}
```

**Template placeholders:**
- `{project_name}` - Project name
- `{budget_percent}` - Budget percentage consumed
- `{budget_consumed}` - Consumed budget amount
- `{budget_total}` - Total budget
- `{days_overdue}` - Days past end date
- `{end_date}` - Project end date
- `{remaining_issues}` - Remaining backlog items
- `{weeks_remaining}` - Weeks until end date
- `{velocity}` - Issues per week velocity
- `{vuln_package}` - Vulnerable package name
- `{vuln_severity}` - Vulnerability severity
- `{vuln_cve}` - CVE identifier
- `{vuln_count}` - Total open vulnerabilities
- `{vuln_age_days}` - Days since first detected

---

## Alert Silences

### List Active Silences

```http
GET /silences?project_id=uuid&include_expired=false
```

**Response:**
```json
[
  {
    "id": 1,
    "project_id": "uuid",
    "project_name": "Project Alpha",
    "alert_definition_id": 1,
    "alert_name": "budget_exceeded",
    "silenced_until": "2024-02-01T00:00:00Z",
    "reason": "Expected budget overrun approved",
    "created_by": "user@example.com",
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

### Create Silence

```http
POST /silences
Content-Type: application/json

{
  "project_id": "uuid",
  "alert_definition_id": 1,
  "silenced_until": "2024-02-01T00:00:00Z",
  "reason": "Expected budget overrun approved"
}
```

**Note:** `alert_definition_id` is optional. If null, silences all alerts for the project.

### Delete Silence

```http
DELETE /silences/{silence_id}
```

---

## Notification Log

### List Notifications

```http
GET /notifications?project_id=uuid&alert_definition_id=1&status=sent&limit=50&offset=0
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "project_id": "uuid",
      "project_name": "Project Alpha",
      "alert_definition_id": 1,
      "alert_name": "budget_exceeded",
      "channel_id": "C1234567890",
      "message": ":warning: *Project Alpha* has exceeded budget (105%)",
      "status": "sent",
      "error_message": null,
      "metadata_json": {"budget_percent": 105.3},
      "sent_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Get Notification Statistics

```http
GET /notifications/stats
```

**Response:**
```json
{
  "total_sent": 150,
  "total_failed": 5,
  "by_alert_type": {
    "budget_exceeded": 45,
    "timeline_at_risk": 30,
    "dependabot_high_critical": 75
  },
  "by_status": {
    "sent": 145,
    "failed": 5
  },
  "last_24_hours": 12,
  "last_7_days": 45,
  "avg_vulnerability_resolution_days": 5.2
}
```

---

## Scheduled Jobs

### List Scheduled Jobs

```http
GET /scheduled-jobs/
```

**Response:**
```json
[
  {
    "name": "check_dependabot_alerts",
    "description": "Check all projects for new Dependabot vulnerabilities",
    "schedule": "Daily at 08:00 UTC",
    "last_run": {
      "started_at": "2024-01-15T08:00:00Z",
      "completed_at": "2024-01-15T08:02:30Z",
      "status": "completed",
      "projects_checked": 15,
      "alerts_sent": 3,
      "error_message": null
    }
  },
  {
    "name": "check_business_alerts",
    "description": "Check all projects for budget/timeline/overdue issues",
    "schedule": "Daily at 09:00 UTC",
    "last_run": {
      "started_at": "2024-01-15T09:00:00Z",
      "completed_at": "2024-01-15T09:01:15Z",
      "status": "completed",
      "projects_checked": 15,
      "alerts_sent": 1,
      "error_message": null
    }
  }
]
```

### Trigger Scheduled Job

```http
POST /scheduled-jobs/{job_name}/trigger
```

**Response:** `202 Accepted`
```json
{
  "message": "Job triggered",
  "job_name": "check_dependabot_alerts"
}
```

---

## Rate Limiting

Rate limiting is active on all endpoints using slowapi:
- Most endpoints: 100 requests/minute
- Config update: 10 requests/minute
- Collectors: 10 requests/minute

**Response when rate limited:**
```json
{
  "detail": "Rate limit exceeded"
}
```
Status code: `429 Too Many Requests`

---

## Versioning

The API is currently at version 1.0.0. Future versions may include breaking changes under new path prefixes (e.g., `/api/v2`).
