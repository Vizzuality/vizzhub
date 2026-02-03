# Dependabot Slack Alerts - Design Document

## Status: Backlog

## Overview

Automatically notify project Slack channels when Dependabot detects critical or high severity vulnerabilities in the project's GitHub repository. Leverages existing project configuration (GitHub repo) and planned Slack integration.

## Motivation

- **Centralized**: No need to configure GitHub Actions or native Slack app per repo
- **Automatic**: Projects already have GitHub repo configured
- **Consistent**: Same notification format across all projects

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ARQ Worker (hourly)                  │
│                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │ GitHub API  │───▶│ Compare with │───▶│ Slack API │  │
│  │ Dependabot  │    │ notified     │    │ (new only)│  │
│  │ Alerts      │    │ alerts       │    │           │  │
│  └─────────────┘    └──────────────┘    └───────────┘  │
│                            │                            │
│                            ▼                            │
│                   ┌────────────────┐                    │
│                   │ DB: tracking   │                    │
│                   │ notified alerts│                    │
│                   └────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

## Data Model

### DependabotNotification Table

```python
class DependabotNotification(Base):
    __tablename__ = "dependabot_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    alert_number: Mapped[int]      # GitHub alert number (unique per repo)
    severity: Mapped[str]          # critical, high
    package_name: Mapped[str]
    cve_id: Mapped[str | None]     # CVE-2024-XXXXX
    notified_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "alert_number", name="uq_project_alert"),
    )
```

### Project Table Addition

```python
# New field in projects table
slack_channel_id: Mapped[str | None]  # Slack channel ID (C0XXXXXX)
```

## API

### GitHub Dependabot Alerts API

```
GET /repos/{owner}/{repo}/dependabot/alerts
  ?state=open
  &severity=critical,high

Headers:
  Authorization: Bearer {github_token}
  Accept: application/vnd.github+json
```

**Required scope**: `security_events` (or repository admin)

**Response example**:
```json
{
  "number": 42,
  "state": "open",
  "security_vulnerability": {
    "severity": "critical",
    "package": {
      "ecosystem": "npm",
      "name": "lodash"
    }
  },
  "security_advisory": {
    "cve_id": "CVE-2024-12345",
    "summary": "Prototype Pollution in lodash"
  }
}
```

### Slack Message Format

```python
async def send_dependabot_alert(
    slack_client: SlackClient,
    channel_id: str,
    alert: DependabotAlert,
    project: Project,
) -> None:
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 {alert.severity.upper()} Security Vulnerability"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Project:*\n{project.name}"},
                {"type": "mrkdwn", "text": f"*Package:*\n`{alert.package_name}`"},
                {"type": "mrkdwn", "text": f"*CVE:*\n{alert.cve_id or 'N/A'}"},
                {"type": "mrkdwn", "text": f"*Ecosystem:*\n{alert.ecosystem}"},
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{alert.summary}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View on GitHub"},
                    "url": alert.html_url
                }
            ]
        }
    ]

    await slack_client.chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text=f"🚨 {alert.severity.upper()}: {alert.package_name} vulnerability in {project.name}"
    )
```

## Worker Task

```python
# app/worker/tasks.py

async def check_dependabot_alerts(ctx: dict) -> dict:
    """
    Periodic task to check Dependabot alerts for all projects.
    Runs every hour via ARQ cron.
    """
    async with get_db_session() as db:
        # Get projects with both GitHub and Slack configured
        projects = await get_projects_with_github_and_slack(db)

        stats = {"checked": 0, "notified": 0, "errors": 0}

        for project in projects:
            try:
                # Fetch open critical/high alerts
                alerts = await fetch_dependabot_alerts(
                    repo=project.github_repo,
                    token=project.github_token,
                    severities=["critical", "high"],
                )

                # Filter out already notified
                new_alerts = await filter_unnotified_alerts(
                    db, project.id, alerts
                )

                # Send notifications
                for alert in new_alerts:
                    await send_dependabot_alert(
                        slack_client,
                        project.slack_channel_id,
                        alert,
                        project,
                    )
                    await mark_alert_notified(db, project.id, alert)
                    stats["notified"] += 1

                stats["checked"] += 1

            except Exception as e:
                logger.error(f"Error checking {project.name}: {e}")
                stats["errors"] += 1

        await db.commit()
        return stats


# Worker settings - add cron job
class WorkerSettings:
    cron_jobs = [
        cron(check_dependabot_alerts, hour={0, 6, 12, 18}),  # Every 6 hours
    ]
```

## Dependencies

### Prerequisites

1. **Slack Integration** (planned feature)
   - Slack Bot with `chat:write` permission
   - `slack_channel_id` field in projects table

2. **GitHub Token Scope**
   - Current OAuth may need `security_events` scope added
   - Or use a separate GitHub App with security alerts permission

### New Dependencies

```toml
# pyproject.toml
slack-sdk = "^3.27.0"
```

## Configuration

```bash
# .env additions
SLACK_BOT_TOKEN=xoxb-xxxx-xxxx-xxxx

# Optional: separate GitHub token for security alerts
GITHUB_SECURITY_TOKEN=ghp_xxxx
```

## Implementation Phases

### Phase 1: Slack Integration (prerequisite)
- [ ] Add `slack_channel_id` to projects table
- [ ] Create Slack client service
- [ ] Add Slack channel configuration in project settings UI

### Phase 2: Dependabot Collector
- [ ] Create `DependabotNotification` model and migration
- [ ] Implement GitHub Dependabot alerts API client
- [ ] Add `security_events` scope to GitHub OAuth (or use App token)

### Phase 3: Worker Task
- [ ] Implement `check_dependabot_alerts` task
- [ ] Add cron schedule to ARQ worker
- [ ] Add task monitoring/logging

### Phase 4: UI (Optional)
- [ ] Show recent Dependabot alerts in project detail
- [ ] Allow re-sending notifications
- [ ] Configure severity thresholds per project

## Estimated Effort

| Component | Effort | Notes |
|-----------|--------|-------|
| Slack client setup | 4h | New integration |
| Model + migration | 1h | Simple table |
| GitHub alerts collector | 3h | Similar to existing collectors |
| Worker task | 2h | ARQ infrastructure exists |
| UI (optional) | 4h | Project settings + alerts list |
| **Total** | **~2 days** | Without optional UI |

## Security Considerations

- Slack Bot token stored securely (env var, not DB)
- GitHub token with minimal required scopes
- Rate limiting on GitHub API calls (5000/hour for authenticated)
- No sensitive data in Slack messages (just package names, CVEs)

## Escalation

Unresolved critical alerts should escalate over time:

```
Day 0: Notify project channel
Day 3: Reminder to project channel
Day 7: Escalate to security/leads channel
```

### Implementation

```python
class DependabotNotification(Base):
    # ... existing fields ...
    reminder_sent_at: Mapped[datetime | None]
    escalated_at: Mapped[datetime | None]


async def check_dependabot_escalations(ctx: dict) -> dict:
    """Daily task to send reminders and escalations."""
    now = datetime.utcnow()

    # Reminders (3+ days, not yet reminded)
    reminders = await get_unresolved_alerts(
        min_age_days=3,
        reminder_sent=False,
    )
    for alert in reminders:
        await send_reminder(alert)
        alert.reminder_sent_at = now

    # Escalations (7+ days, not yet escalated)
    escalations = await get_unresolved_alerts(
        min_age_days=7,
        escalated=False,
    )
    for alert in escalations:
        await send_to_security_channel(alert)
        alert.escalated_at = now
```

### Configuration

```bash
# .env
SLACK_SECURITY_CHANNEL_ID=C0XXXXXX  # Escalation channel
DEPENDABOT_REMINDER_DAYS=3
DEPENDABOT_ESCALATION_DAYS=7
```

## Future Enhancements

- [ ] Configurable severity threshold per project (e.g., only critical)
- [ ] Daily digest mode instead of real-time
- [ ] Auto-create GitHub issues for critical alerts
