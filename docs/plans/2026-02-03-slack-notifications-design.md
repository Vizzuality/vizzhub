# Slack Notifications System Design

**Date:** 2026-02-03
**Status:** Draft

## Overview

A configurable Slack notification system for Project Scorecard that sends alerts to project-specific channels and a leadership channel based on predefined rules.

## Goals

- Alert project teams about security vulnerabilities (Dependabot)
- Alert leadership about budget overruns, timeline risks, and overdue projects
- Provide per-project silencing with optional time limits
- Full visibility into notification history and scheduled jobs

## Alert Types

### Business Alerts (→ Leadership Channel)

| Alert | Trigger Condition | Schedule |
|-------|-------------------|----------|
| Budget Exceeded | `budget_consumed / budget_total >= 1.0` | Daily check, monthly report |
| Timeline at Risk | Velocity suggests won't complete by `end_date` | Daily check, monthly report |
| Project Overdue | `current_date > end_date + 1 month` | Daily check, monthly report |

- Checked daily, but only one notification per project per month (throttling)
- Stop when project status = finished

### Project Alerts (→ Project Channel)

| Alert | Trigger Condition | Schedule |
|-------|-------------------|----------|
| Dependabot Critical/High | New vulnerability detected | Immediate on discovery |
| Dependabot Reminder | Unresolved vulnerability exists | Daily until resolved |

- Track individual vulnerabilities to avoid duplicate "new finding" alerts
- Daily reminders for unresolved vulnerabilities

## Data Model

### New Tables

**`slack_config`** (single row, global settings)
```sql
CREATE TABLE slack_config (
    id SERIAL PRIMARY KEY,
    bot_token_encrypted TEXT NOT NULL,
    leadership_channel_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**`alert_definitions`** (predefined alert types)
```sql
CREATE TABLE alert_definitions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,  -- 'business' | 'project'
    channel_type VARCHAR(50) NOT NULL,  -- 'leadership' | 'project'
    schedule VARCHAR(50) NOT NULL,  -- 'daily_check_monthly_report' | 'daily'
    is_enabled BOOLEAN DEFAULT TRUE,
    config_json JSONB,  -- thresholds, e.g., {"budget_percent": 100}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**`message_templates`** (customizable message text)
```sql
CREATE TABLE message_templates (
    id SERIAL PRIMARY KEY,
    alert_definition_id INTEGER REFERENCES alert_definitions(id),
    template_type VARCHAR(50) NOT NULL,  -- 'initial' | 'reminder' | 'escalation'
    message_template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**`alert_silences`** (per-project muting)
```sql
CREATE TABLE alert_silences (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    alert_definition_id INTEGER REFERENCES alert_definitions(id),  -- NULL = all alerts
    silenced_until TIMESTAMP,  -- NULL = indefinite
    reason TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**`alert_notifications`** (log of sent alerts)
```sql
CREATE TABLE alert_notifications (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    alert_definition_id INTEGER REFERENCES alert_definitions(id),
    channel_id VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'sent' | 'failed'
    error_message TEXT,
    metadata_json JSONB,  -- vulnerability ID, threshold value, etc.
    sent_at TIMESTAMP DEFAULT NOW()
);
```

**`dependabot_alerts_tracked`** (for deduplication)
```sql
CREATE TABLE dependabot_alerts_tracked (
    id SERIAL PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    github_alert_id INTEGER NOT NULL,
    package_name VARCHAR(200),
    severity VARCHAR(20),
    cve_id VARCHAR(50),
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_notified_at TIMESTAMP,
    resolved_at TIMESTAMP,
    UNIQUE(project_id, github_alert_id)
);
```

**`scheduled_job_runs`** (job tracking)
```sql
CREATE TABLE scheduled_job_runs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,  -- 'running' | 'success' | 'failed'
    projects_checked INTEGER DEFAULT 0,
    alerts_sent INTEGER DEFAULT 0,
    error_message TEXT
);
```

### Table Modifications

**`projects`** - Add column:
```sql
ALTER TABLE projects ADD COLUMN slack_channel_id VARCHAR(50);
```

## Message Templates

### Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{project_name}` | Project name |
| `{project_key}` | Jira project key |
| `{budget_consumed}` | Amount spent |
| `{budget_total}` | Total budget |
| `{budget_percent}` | Percentage consumed |
| `{end_date}` | Planned end date |
| `{days_overdue}` | Days past end date |
| `{velocity}` | Current velocity (issues/week) |
| `{remaining_issues}` | Issues remaining |
| `{weeks_remaining}` | Weeks until end date |
| `{vuln_package}` | Package with vulnerability |
| `{vuln_severity}` | Critical/High |
| `{vuln_cve}` | CVE identifier |
| `{vuln_age_days}` | Days since detected |
| `{vuln_count}` | Total open vulnerabilities |

### Default Templates

**Budget Exceeded (initial):**
```
:warning: *{project_name}* has exceeded budget ({budget_percent}% consumed)
Budget: ${budget_consumed} / ${budget_total}
```

**Timeline at Risk (initial):**
```
:warning: *{project_name}* timeline at risk
{remaining_issues} issues remaining | {weeks_remaining} weeks left | Velocity: {velocity}/week
```

**Project Overdue (initial):**
```
:rotating_light: *{project_name}* is {days_overdue} days past planned end date
Planned end: {end_date}
```

**Dependabot (initial):**
```
:red_circle: New {vuln_severity} vulnerability in *{project_name}*
Package: {vuln_package}
CVE: {vuln_cve}
```

**Dependabot (reminder):**
```
:alarm_clock: *{project_name}* has {vuln_count} open high/critical vulnerabilities
Oldest unresolved: {vuln_age_days} days
```

## Background Jobs

### Job: `check_dependabot_alerts`

**Schedule:** Daily at 8:00 AM

**Logic:**
1. Create `scheduled_job_runs` record (status: running)
2. Get all active projects with GitHub repo configured
3. For each project:
   - Skip if project finished or silenced for Dependabot alerts
   - Call GitHub Dependabot API for high/critical alerts
   - Compare against `dependabot_alerts_tracked`:
     - New alerts → send notification, add to tracked
     - Existing unresolved → send daily reminder
     - Resolved in GitHub → mark `resolved_at` in tracked
   - Log all notifications to `alert_notifications`
4. Update job run record (status: success/failed, counts)

### Job: `check_business_alerts`

**Schedule:** Daily at 9:00 AM

**Logic:**
1. Create `scheduled_job_runs` record (status: running)
2. Get all active projects (skip finished)
3. For each project, check each business alert:
   - Skip if project silenced for this alert type
   - **Budget:** `budget_consumed / budget_total >= 1.0`
   - **Timeline:** Calculate `remaining_issues / velocity > weeks_remaining`
   - **Overdue:** `current_date > end_date + 30 days`
4. For triggered alerts:
   - Check `alert_notifications` for same project/alert this month
   - If already notified → skip (monthly throttle)
   - If not → send to leadership channel, log notification
5. Update job run record (status: success/failed, counts)

### ARQ Configuration

```python
# worker/settings.py
from arq.cron import cron

cron_jobs = [
    cron(check_dependabot_alerts, hour=8, minute=0),
    cron(check_business_alerts, hour=9, minute=0),
]
```

## Slack Integration

### Slack App Setup

1. Create Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes:
   - `chat:write.public` - Post to any public channel
   - `chat:write` - Post to private channels (when invited)
   - `channels:read` - List public channels for dropdown
   - `groups:read` - List private channels bot is member of
3. Install to workspace
4. Copy Bot Token (`xoxb-...`) to app settings
5. Invite bot to leadership channel: `/invite @BotName`

### Channel Access

| Channel Type | Access |
|--------------|--------|
| Public (project channels) | Automatic via `chat:write.public` |
| Private (leadership) | Requires `/invite @bot` once |

## API Endpoints

### Slack Configuration

```
GET    /api/admin/slack/config         - Get config (token masked)
PUT    /api/admin/slack/config         - Update bot token, leadership channel
POST   /api/admin/slack/test           - Test connection / send test message
GET    /api/admin/slack/channels       - List available channels from Slack
```

### Alert Definitions

```
GET    /api/admin/alerts               - List all alert definitions
PUT    /api/admin/alerts/{id}          - Update (enable/disable, thresholds)
POST   /api/admin/alerts/{id}/test     - Send test notification
```

### Message Templates

```
GET    /api/admin/alerts/{id}/templates    - Get templates for alert
PUT    /api/admin/templates/{id}           - Update template text
```

### Silences

```
GET    /api/silences                   - List all active silences
POST   /api/silences                   - Create silence
PUT    /api/silences/{id}              - Update silence
DELETE /api/silences/{id}              - Remove silence
```

**Create silence request:**
```json
{
    "project_id": "uuid",
    "alert_definition_id": 1,  // null = all alerts
    "silenced_until": "2026-03-01T00:00:00Z",  // null = indefinite
    "reason": "Maintenance period"
}
```

### Alert Log

```
GET    /api/notifications              - List sent notifications
GET    /api/notifications/stats        - Aggregated statistics
```

**Query parameters for notifications:**
- `project_id` - Filter by project
- `alert_definition_id` - Filter by alert type
- `start_date`, `end_date` - Date range
- `page`, `page_size` - Pagination

### Scheduled Jobs

```
GET    /api/admin/jobs/scheduled       - List scheduled jobs with status
POST   /api/admin/jobs/scheduled/{name}/run  - Manual trigger
```

## Frontend

### New Page: `/admin/notifications`

**Tabs:**

1. **Alert Log**
   - Table: Timestamp, Project, Alert Type, Channel, Message, Status
   - Filters: Project, Alert Type, Date Range
   - Pagination

2. **Active Silences**
   - Table: Project, Alert Type, Until, Reason, Actions
   - Add/Edit/Remove silences

3. **Alert Configuration**
   - List alerts with enable/disable toggles
   - Edit thresholds
   - Edit message templates
   - Test buttons

4. **Statistics**
   - Alerts this month (by type)
   - Most alerted projects
   - Avg vulnerability resolution time
   - Last job run times

### Jobs Page Updates (`/admin/jobs`)

**New section: Scheduled Jobs**

| Job Name | Schedule | Last Run | Status | Next Run | Actions |
|----------|----------|----------|--------|----------|---------|
| Dependabot Check | Daily 8:00 AM | Feb 3, 8:00 AM | Success | Feb 4, 8:00 AM | Run Now |
| Business Alerts | Daily 9:00 AM | Feb 3, 9:00 AM | Success | Feb 4, 9:00 AM | Run Now |

- Click job → view run details (projects checked, alerts sent, errors)

### Project Edit Form

Add field:
- **Slack Channel** - Dropdown populated from Slack API

### App Settings

Add section:
- **Slack Bot Token** - Masked input field
- **Leadership Channel** - Dropdown from Slack API
- **Test Connection** button
- **Send Test Message** button

## Seed Data

### Default Alert Definitions

```csv
name,category,channel_type,schedule,is_enabled,config_json
Budget Exceeded,business,leadership,daily_check_monthly_report,true,"{}"
Timeline at Risk,business,leadership,daily_check_monthly_report,true,"{}"
Project Overdue,business,leadership,daily_check_monthly_report,true,"{\"grace_days\": 30}"
Dependabot High/Critical,project,project,daily,true,"{\"severities\": [\"critical\", \"high\"]}"
```

## Security Considerations

- Bot token stored encrypted in database
- Token masked in API responses and UI
- Only admins can access `/api/admin/*` endpoints
- Validate channel IDs exist before saving
- Rate limit Slack API calls (respect Slack's limits)

## Future Enhancements

- Rule builder for custom alert conditions
- Escalation paths (alert → reminder → escalate to different channel)
- Digest mode (daily summary instead of individual alerts)
- Email as alternative notification channel
- Webhook support for other integrations
