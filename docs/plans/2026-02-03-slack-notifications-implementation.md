# Slack Notifications System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a Slack notification system that alerts project channels about Dependabot vulnerabilities and leadership channel about budget/timeline issues.

**Architecture:** Backend adds 7 new tables, 2 cron jobs, and Slack service. Frontend adds notifications admin page and project channel field.

**Tech Stack:** FastAPI, SQLAlchemy, ARQ cron jobs, httpx for Slack API, React, TanStack Query

---

## Phase 1: Database Models & Migrations

### Task 1: Create Slack Config Model

**Files:**
- Create: `backend/app/models/slack.py`
- Test: `backend/tests/test_slack_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_slack_models.py
import pytest
from app.models.slack import SlackConfigDB, AlertDefinitionDB, MessageTemplateDB

def test_slack_config_model_exists():
    assert SlackConfigDB.__tablename__ == "slack_config"

def test_alert_definition_model_exists():
    assert AlertDefinitionDB.__tablename__ == "alert_definitions"

def test_message_template_model_exists():
    assert MessageTemplateDB.__tablename__ == "message_templates"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_slack_models.py -v`
Expected: FAIL with "cannot import name 'SlackConfigDB'"

**Step 3: Write minimal implementation**

```python
# backend/app/models/slack.py
"""Slack notification models."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AlertCategory(str, Enum):
    BUSINESS = "business"
    PROJECT = "project"


class ChannelType(str, Enum):
    LEADERSHIP = "leadership"
    PROJECT = "project"


class AlertSchedule(str, Enum):
    DAILY_CHECK_MONTHLY_REPORT = "daily_check_monthly_report"
    DAILY = "daily"


class TemplateType(str, Enum):
    INITIAL = "initial"
    REMINDER = "reminder"
    ESCALATION = "escalation"


class SlackConfigDB(Base):
    """Global Slack configuration (single row)."""

    __tablename__ = "slack_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    leadership_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertDefinitionDB(Base):
    """Predefined alert types."""

    __tablename__ = "alert_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule: Mapped[str] = mapped_column(String(50), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MessageTemplateDB(Base):
    """Customizable message templates."""

    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=False
    )
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_slack_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/slack.py backend/tests/test_slack_models.py
git commit -m "feat(models): add Slack config, alert definitions, message templates"
```

---

### Task 2: Create Alert Tracking Models

**Files:**
- Modify: `backend/app/models/slack.py`
- Test: `backend/tests/test_slack_models.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_slack_models.py
from app.models.slack import (
    AlertSilenceDB,
    AlertNotificationDB,
    DependabotAlertTrackedDB,
    ScheduledJobRunDB,
)

def test_alert_silence_model_exists():
    assert AlertSilenceDB.__tablename__ == "alert_silences"

def test_alert_notification_model_exists():
    assert AlertNotificationDB.__tablename__ == "alert_notifications"

def test_dependabot_alert_tracked_model_exists():
    assert DependabotAlertTrackedDB.__tablename__ == "dependabot_alerts_tracked"

def test_scheduled_job_run_model_exists():
    assert ScheduledJobRunDB.__tablename__ == "scheduled_job_runs"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_slack_models.py::test_alert_silence_model_exists -v`
Expected: FAIL with "cannot import name 'AlertSilenceDB'"

**Step 3: Write minimal implementation**

```python
# Add to backend/app/models/slack.py
from uuid import UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class AlertSilenceDB(Base):
    """Per-project alert muting."""

    __tablename__ = "alert_silences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    alert_definition_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=True
    )
    silenced_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertNotificationDB(Base):
    """Log of sent alerts."""

    __tablename__ = "alert_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    alert_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DependabotAlertTrackedDB(Base):
    """Track notified Dependabot alerts for deduplication."""

    __tablename__ = "dependabot_alerts_tracked"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    github_alert_id: Mapped[int] = mapped_column(Integer, nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cve_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ScheduledJobRunDB(Base):
    """Track scheduled job executions."""

    __tablename__ = "scheduled_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    projects_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alerts_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_slack_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/slack.py backend/tests/test_slack_models.py
git commit -m "feat(models): add alert tracking models (silences, notifications, dependabot)"
```

---

### Task 3: Add slack_channel_id to Project Model

**Files:**
- Modify: `backend/app/models/project.py`
- Test: `backend/tests/test_project_model.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_project_model.py (add to existing or create)
from app.models.project import ProjectDB, ProjectUpdate

def test_project_has_slack_channel_id():
    assert hasattr(ProjectDB, "slack_channel_id")

def test_project_update_has_slack_channel_id():
    update = ProjectUpdate(slack_channel_id="C123456")
    assert update.slack_channel_id == "C123456"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_project_model.py::test_project_has_slack_channel_id -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `backend/app/models/project.py`:

Add to `ProjectDB` class:
```python
slack_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

Add to `ProjectBase` class:
```python
slack_channel_id: str | None = Field(None, max_length=50)
```

Add to `ProjectUpdate` class:
```python
slack_channel_id: str | None = Field(None, max_length=50)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_project_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/project.py backend/tests/test_project_model.py
git commit -m "feat(models): add slack_channel_id to Project model"
```

---

### Task 4: Create Database Migration

**Files:**
- Create: `backend/alembic/versions/011_add_slack_notifications.py`

**Step 1: Create migration file**

```python
# backend/alembic/versions/011_add_slack_notifications.py
"""Add Slack notifications tables

Revision ID: 011_add_slack_notifications
Revises: 010_add_global_metrics_table
Create Date: 2026-02-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "011_add_slack_notifications"
down_revision: Union[str, None] = "010_add_global_metrics_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add slack_channel_id to projects
    op.add_column("projects", sa.Column("slack_channel_id", sa.String(50), nullable=True))

    # slack_config table
    op.create_table(
        "slack_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=True),
        sa.Column("leadership_channel_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # alert_definitions table
    op.create_table(
        "alert_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("schedule", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # message_templates table
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_definition_id", sa.Integer(), sa.ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # alert_silences table
    op.create_table(
        "alert_silences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_definition_id", sa.Integer(), sa.ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("silenced_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_silences_project_id", "alert_silences", ["project_id"])

    # alert_notifications table
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_definition_id", sa.Integer(), sa.ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_notifications_project_id", "alert_notifications", ["project_id"])
    op.create_index("ix_alert_notifications_sent_at", "alert_notifications", ["sent_at"])

    # dependabot_alerts_tracked table
    op.create_table(
        "dependabot_alerts_tracked",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_alert_id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(200), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("cve_id", sa.String(50), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "github_alert_id", name="uq_dependabot_project_alert"),
    )
    op.create_index("ix_dependabot_alerts_project_id", "dependabot_alerts_tracked", ["project_id"])

    # scheduled_job_runs table
    op.create_table(
        "scheduled_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("projects_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_scheduled_job_runs_job_name", "scheduled_job_runs", ["job_name"])
    op.create_index("ix_scheduled_job_runs_started_at", "scheduled_job_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_job_runs_started_at", table_name="scheduled_job_runs")
    op.drop_index("ix_scheduled_job_runs_job_name", table_name="scheduled_job_runs")
    op.drop_table("scheduled_job_runs")

    op.drop_index("ix_dependabot_alerts_project_id", table_name="dependabot_alerts_tracked")
    op.drop_table("dependabot_alerts_tracked")

    op.drop_index("ix_alert_notifications_sent_at", table_name="alert_notifications")
    op.drop_index("ix_alert_notifications_project_id", table_name="alert_notifications")
    op.drop_table("alert_notifications")

    op.drop_index("ix_alert_silences_project_id", table_name="alert_silences")
    op.drop_table("alert_silences")

    op.drop_table("message_templates")
    op.drop_table("alert_definitions")
    op.drop_table("slack_config")

    op.drop_column("projects", "slack_channel_id")
```

**Step 2: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Verify tables exist**

Run: `cd backend && python -c "from app.database import engine; print('OK')"`

**Step 4: Commit**

```bash
git add backend/alembic/versions/011_add_slack_notifications.py
git commit -m "feat(db): add migration for Slack notifications tables"
```

---

### Task 5: Create Seed Data for Alert Definitions

**Files:**
- Create: `backend/seeds/alert_definitions.csv`
- Create: `backend/seeds/message_templates.csv`

**Step 1: Create alert definitions seed**

```csv
# backend/seeds/alert_definitions.csv
name,description,category,channel_type,schedule,is_enabled,config_json
budget_exceeded,Project budget has been fully consumed,business,leadership,daily_check_monthly_report,true,"{}"
timeline_at_risk,Project velocity suggests timeline risk,business,leadership,daily_check_monthly_report,true,"{}"
project_overdue,Project is more than 30 days past end date,business,leadership,daily_check_monthly_report,true,"{\"grace_days\": 30}"
dependabot_high_critical,High or critical Dependabot vulnerability detected,project,project,daily,true,"{\"severities\": [\"critical\", \"high\"]}"
```

**Step 2: Create message templates seed**

```csv
# backend/seeds/message_templates.csv
alert_name,template_type,message_template,is_active
budget_exceeded,initial,":warning: *{project_name}* has exceeded budget ({budget_percent}% consumed)\nBudget: ${budget_consumed} / ${budget_total}",true
timeline_at_risk,initial,":warning: *{project_name}* timeline at risk\n{remaining_issues} issues remaining | {weeks_remaining} weeks left | Velocity: {velocity}/week",true
project_overdue,initial,":rotating_light: *{project_name}* is {days_overdue} days past planned end date\nPlanned end: {end_date}",true
dependabot_high_critical,initial,":red_circle: New {vuln_severity} vulnerability in *{project_name}*\nPackage: {vuln_package}\nCVE: {vuln_cve}",true
dependabot_high_critical,reminder,":alarm_clock: *{project_name}* has {vuln_count} open high/critical vulnerabilities\nOldest unresolved: {vuln_age_days} days",true
```

**Step 3: Commit**

```bash
git add backend/seeds/alert_definitions.csv backend/seeds/message_templates.csv
git commit -m "feat(seeds): add alert definitions and message templates"
```

---

## Phase 2: Slack Service & Core Logic

### Task 6: Create Slack Service

**Files:**
- Create: `backend/app/services/slack_service.py`
- Test: `backend/tests/test_slack_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_slack_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.slack_service import SlackService

@pytest.mark.asyncio
async def test_send_message_success():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"ok": True}
        )

        result = await SlackService.send_message(
            bot_token="xoxb-test",
            channel_id="C123",
            message="Test message"
        )

        assert result["ok"] is True

@pytest.mark.asyncio
async def test_list_channels():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "ok": True,
                "channels": [{"id": "C123", "name": "general"}]
            }
        )

        channels = await SlackService.list_channels("xoxb-test")

        assert len(channels) == 1
        assert channels[0]["name"] == "general"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_slack_service.py -v`
Expected: FAIL with "cannot import name 'SlackService'"

**Step 3: Write minimal implementation**

```python
# backend/app/services/slack_service.py
"""Slack API service."""
import httpx
from typing import Any


class SlackService:
    """Service for interacting with Slack API."""

    BASE_URL = "https://slack.com/api"

    @staticmethod
    async def send_message(
        bot_token: str,
        channel_id: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a message to a Slack channel."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SlackService.BASE_URL}/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={
                    "channel": channel_id,
                    "text": message,
                    "mrkdwn": True,
                },
            )
            return response.json()

    @staticmethod
    async def list_channels(bot_token: str) -> list[dict[str, Any]]:
        """List available Slack channels."""
        channels = []
        cursor = None

        async with httpx.AsyncClient() as client:
            while True:
                params = {"types": "public_channel,private_channel", "limit": 200}
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    f"{SlackService.BASE_URL}/conversations.list",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    params=params,
                )
                data = response.json()

                if not data.get("ok"):
                    break

                channels.extend(data.get("channels", []))

                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        return channels

    @staticmethod
    async def test_connection(bot_token: str) -> dict[str, Any]:
        """Test Slack bot token validity."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SlackService.BASE_URL}/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            return response.json()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_slack_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/slack_service.py backend/tests/test_slack_service.py
git commit -m "feat(services): add Slack API service"
```

---

### Task 7: Create Alert Service

**Files:**
- Create: `backend/app/services/alert_service.py`
- Test: `backend/tests/test_alert_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_alert_service.py
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from app.services.alert_service import AlertService

def test_render_template_basic():
    template = "Project {project_name} has {budget_percent}% budget used"
    context = {"project_name": "Test Project", "budget_percent": 85}

    result = AlertService.render_template(template, context)

    assert result == "Project Test Project has 85% budget used"

def test_render_template_missing_placeholder():
    template = "Project {project_name} has {missing_field}"
    context = {"project_name": "Test Project"}

    result = AlertService.render_template(template, context)

    assert "{missing_field}" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_alert_service.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# backend/app/services/alert_service.py
"""Alert management service."""
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
)


class AlertService:
    """Service for managing alerts."""

    @staticmethod
    def render_template(template: str, context: dict[str, Any]) -> str:
        """Render a message template with context values."""
        def replace_placeholder(match: re.Match) -> str:
            key = match.group(1)
            return str(context.get(key, match.group(0)))

        return re.sub(r"\{(\w+)\}", replace_placeholder, template)

    @staticmethod
    async def is_silenced(
        db: AsyncSession,
        project_id: UUID,
        alert_definition_id: int | None = None,
    ) -> bool:
        """Check if alerts are silenced for a project."""
        now = datetime.now(timezone.utc)

        query = select(AlertSilenceDB).where(
            AlertSilenceDB.project_id == project_id,
            # Either silence all alerts (null) or this specific alert
            (AlertSilenceDB.alert_definition_id.is_(None)) |
            (AlertSilenceDB.alert_definition_id == alert_definition_id),
            # Either indefinite (null) or not yet expired
            (AlertSilenceDB.silenced_until.is_(None)) |
            (AlertSilenceDB.silenced_until > now),
        )

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def was_notified_this_month(
        db: AsyncSession,
        project_id: UUID,
        alert_definition_id: int,
    ) -> bool:
        """Check if this alert was already sent this month for this project."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = select(AlertNotificationDB).where(
            AlertNotificationDB.project_id == project_id,
            AlertNotificationDB.alert_definition_id == alert_definition_id,
            AlertNotificationDB.sent_at >= month_start,
            AlertNotificationDB.status == "sent",
        )

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_template(
        db: AsyncSession,
        alert_definition_id: int,
        template_type: str = "initial",
    ) -> str | None:
        """Get the message template for an alert."""
        query = select(MessageTemplateDB).where(
            MessageTemplateDB.alert_definition_id == alert_definition_id,
            MessageTemplateDB.template_type == template_type,
            MessageTemplateDB.is_active == True,
        )

        result = await db.execute(query)
        template = result.scalar_one_or_none()
        return template.message_template if template else None

    @staticmethod
    async def log_notification(
        db: AsyncSession,
        project_id: UUID,
        alert_definition_id: int,
        channel_id: str,
        message: str,
        status: str,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> AlertNotificationDB:
        """Log a sent notification."""
        notification = AlertNotificationDB(
            project_id=project_id,
            alert_definition_id=alert_definition_id,
            channel_id=channel_id,
            message=message,
            status=status,
            error_message=error_message,
            metadata_json=metadata,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_alert_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/alert_service.py backend/tests/test_alert_service.py
git commit -m "feat(services): add alert service with template rendering"
```

---

## Phase 3: Background Jobs

### Task 8: Create Dependabot Collector

**Files:**
- Create: `backend/app/services/collectors/dependabot.py`
- Test: `backend/tests/test_dependabot_collector.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_dependabot_collector.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.collectors.dependabot import DependabotCollector

@pytest.mark.asyncio
async def test_fetch_alerts_returns_high_critical():
    mock_alerts = [
        {"number": 1, "security_vulnerability": {"severity": "critical"}, "state": "open"},
        {"number": 2, "security_vulnerability": {"severity": "high"}, "state": "open"},
        {"number": 3, "security_vulnerability": {"severity": "low"}, "state": "open"},
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: mock_alerts
        mock_get.return_value = mock_response

        alerts = await DependabotCollector.fetch_alerts("owner/repo", "token")

        # Should only return critical and high
        assert len(alerts) == 2
        assert all(a["security_vulnerability"]["severity"] in ["critical", "high"] for a in alerts)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_dependabot_collector.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# backend/app/services/collectors/dependabot.py
"""Dependabot alerts collector."""
import httpx
from typing import Any


class DependabotCollector:
    """Collector for GitHub Dependabot alerts."""

    GITHUB_API = "https://api.github.com"
    TARGET_SEVERITIES = {"critical", "high"}

    @staticmethod
    async def fetch_alerts(
        repo: str,
        token: str,
    ) -> list[dict[str, Any]]:
        """Fetch open high/critical Dependabot alerts for a repo."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DependabotCollector.GITHUB_API}/repos/{repo}/dependabot/alerts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"state": "open", "per_page": 100},
            )

            if response.status_code != 200:
                return []

            alerts = response.json()

            return [
                alert for alert in alerts
                if alert.get("security_vulnerability", {}).get("severity", "").lower()
                in DependabotCollector.TARGET_SEVERITIES
            ]

    @staticmethod
    def extract_alert_info(alert: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant info from a Dependabot alert."""
        vuln = alert.get("security_vulnerability", {})
        advisory = alert.get("security_advisory", {})

        return {
            "github_alert_id": alert.get("number"),
            "package_name": vuln.get("package", {}).get("name"),
            "severity": vuln.get("severity"),
            "cve_id": next(
                (i["value"] for i in advisory.get("identifiers", []) if i["type"] == "CVE"),
                None,
            ),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_dependabot_collector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/collectors/dependabot.py backend/tests/test_dependabot_collector.py
git commit -m "feat(collectors): add Dependabot alerts collector"
```

---

### Task 9: Create Dependabot Check Job

**Files:**
- Create: `backend/app/worker/check_dependabot.py`
- Test: `backend/tests/test_check_dependabot_job.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_check_dependabot_job.py
import pytest
from app.worker.check_dependabot import check_dependabot_alerts

def test_check_dependabot_job_exists():
    assert callable(check_dependabot_alerts)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_check_dependabot_job.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/worker/check_dependabot.py
"""Dependabot alerts check job."""
import traceback
from datetime import datetime, timezone

from sqlalchemy import select, and_

from app.config import get_settings
from app.models.project import ProjectDB, ProjectStatus
from app.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
    ScheduledJobRunDB,
    SlackConfigDB,
)
from app.services.alert_service import AlertService
from app.services.collectors.dependabot import DependabotCollector
from app.services.slack_service import SlackService


async def check_dependabot_alerts(ctx: dict) -> dict:
    """Check all projects for new Dependabot alerts."""
    db = ctx["db"]
    settings = get_settings()
    now = datetime.now(timezone.utc)

    # Create job run record
    job_run = ScheduledJobRunDB(
        job_name="check_dependabot_alerts",
        status="running",
    )
    db.add(job_run)
    await db.commit()

    projects_checked = 0
    alerts_sent = 0

    try:
        # Get Slack config
        config_result = await db.execute(select(SlackConfigDB).limit(1))
        slack_config = config_result.scalar_one_or_none()

        if not slack_config or not slack_config.bot_token_encrypted:
            job_run.status = "failed"
            job_run.error_message = "Slack not configured"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"error": "Slack not configured"}

        # Get Dependabot alert definition
        alert_def_result = await db.execute(
            select(AlertDefinitionDB).where(
                AlertDefinitionDB.name == "dependabot_high_critical",
                AlertDefinitionDB.is_enabled == True,
            )
        )
        alert_def = alert_def_result.scalar_one_or_none()

        if not alert_def:
            job_run.status = "completed"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"skipped": "Alert definition disabled or missing"}

        # Get active projects with GitHub repos
        projects_result = await db.execute(
            select(ProjectDB).where(
                ProjectDB.status == ProjectStatus.IN_PROGRESS,
                ProjectDB.github_repo.isnot(None),
                ProjectDB.slack_channel_id.isnot(None),
            )
        )
        projects = projects_result.scalars().all()

        for project in projects:
            projects_checked += 1

            # Check if silenced
            if await AlertService.is_silenced(db, project.id, alert_def.id):
                continue

            # Fetch current alerts from GitHub
            current_alerts = await DependabotCollector.fetch_alerts(
                project.github_repo,
                settings.github_token,
            )

            # Get tracked alerts
            tracked_result = await db.execute(
                select(DependabotAlertTrackedDB).where(
                    DependabotAlertTrackedDB.project_id == project.id,
                    DependabotAlertTrackedDB.resolved_at.is_(None),
                )
            )
            tracked = {t.github_alert_id: t for t in tracked_result.scalars().all()}

            current_alert_ids = {a["number"] for a in current_alerts}

            # Mark resolved alerts
            for alert_id, tracked_alert in tracked.items():
                if alert_id not in current_alert_ids:
                    tracked_alert.resolved_at = now
                    await db.commit()

            # Process current alerts
            for alert in current_alerts:
                info = DependabotCollector.extract_alert_info(alert)
                alert_id = info["github_alert_id"]

                if alert_id in tracked:
                    # Existing alert - send reminder
                    tracked_alert = tracked[alert_id]
                    template = await AlertService.get_template(db, alert_def.id, "reminder")
                    if template:
                        # Count open alerts for reminder
                        context = {
                            "project_name": project.name,
                            "vuln_count": len(current_alerts),
                            "vuln_age_days": (now - tracked_alert.first_seen_at).days,
                        }
                        message = AlertService.render_template(template, context)

                        result = await SlackService.send_message(
                            slack_config.bot_token_encrypted,
                            project.slack_channel_id,
                            message,
                        )

                        await AlertService.log_notification(
                            db, project.id, alert_def.id,
                            project.slack_channel_id, message,
                            "sent" if result.get("ok") else "failed",
                            metadata={"type": "reminder", "vuln_count": len(current_alerts)},
                        )

                        if result.get("ok"):
                            alerts_sent += 1
                            tracked_alert.last_notified_at = now
                            await db.commit()
                else:
                    # New alert - track and notify
                    new_tracked = DependabotAlertTrackedDB(
                        project_id=project.id,
                        github_alert_id=alert_id,
                        package_name=info["package_name"],
                        severity=info["severity"],
                        cve_id=info["cve_id"],
                        last_notified_at=now,
                    )
                    db.add(new_tracked)
                    await db.commit()

                    template = await AlertService.get_template(db, alert_def.id, "initial")
                    if template:
                        context = {
                            "project_name": project.name,
                            "vuln_package": info["package_name"],
                            "vuln_severity": info["severity"],
                            "vuln_cve": info["cve_id"] or "N/A",
                        }
                        message = AlertService.render_template(template, context)

                        result = await SlackService.send_message(
                            slack_config.bot_token_encrypted,
                            project.slack_channel_id,
                            message,
                        )

                        await AlertService.log_notification(
                            db, project.id, alert_def.id,
                            project.slack_channel_id, message,
                            "sent" if result.get("ok") else "failed",
                            metadata={"type": "initial", **info},
                        )

                        if result.get("ok"):
                            alerts_sent += 1

        job_run.status = "success"
        job_run.projects_checked = projects_checked
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "projects_checked": projects_checked,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        job_run.status = "failed"
        job_run.error_message = str(e)
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_check_dependabot_job.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/worker/check_dependabot.py backend/tests/test_check_dependabot_job.py
git commit -m "feat(worker): add Dependabot check scheduled job"
```

---

### Task 10: Create Business Alerts Check Job

**Files:**
- Create: `backend/app/worker/check_business_alerts.py`
- Test: `backend/tests/test_check_business_alerts_job.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_check_business_alerts_job.py
import pytest
from app.worker.check_business_alerts import check_business_alerts

def test_check_business_alerts_job_exists():
    assert callable(check_business_alerts)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_check_business_alerts_job.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/worker/check_business_alerts.py
"""Business alerts check job."""
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.models.project import ProjectDB, ProjectStatus
from app.models.slack import (
    AlertDefinitionDB,
    ScheduledJobRunDB,
    SlackConfigDB,
)
from app.services.alert_service import AlertService
from app.services.slack_service import SlackService


async def check_business_alerts(ctx: dict) -> dict:
    """Check all projects for business alert conditions."""
    db = ctx["db"]
    now = datetime.now(timezone.utc)
    today = now.date()

    # Create job run record
    job_run = ScheduledJobRunDB(
        job_name="check_business_alerts",
        status="running",
    )
    db.add(job_run)
    await db.commit()

    projects_checked = 0
    alerts_sent = 0

    try:
        # Get Slack config
        config_result = await db.execute(select(SlackConfigDB).limit(1))
        slack_config = config_result.scalar_one_or_none()

        if not slack_config or not slack_config.bot_token_encrypted:
            job_run.status = "failed"
            job_run.error_message = "Slack not configured"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"error": "Slack not configured"}

        if not slack_config.leadership_channel_id:
            job_run.status = "failed"
            job_run.error_message = "Leadership channel not configured"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"error": "Leadership channel not configured"}

        # Get enabled business alert definitions
        alert_defs_result = await db.execute(
            select(AlertDefinitionDB).where(
                AlertDefinitionDB.category == "business",
                AlertDefinitionDB.is_enabled == True,
            )
        )
        alert_defs = {a.name: a for a in alert_defs_result.scalars().all()}

        # Get active projects
        projects_result = await db.execute(
            select(ProjectDB).where(
                ProjectDB.status == ProjectStatus.IN_PROGRESS,
            )
        )
        projects = projects_result.scalars().all()

        for project in projects:
            projects_checked += 1

            # Check budget exceeded
            if "budget_exceeded" in alert_defs:
                alert_def = alert_defs["budget_exceeded"]

                if not await AlertService.is_silenced(db, project.id, alert_def.id):
                    if not await AlertService.was_notified_this_month(db, project.id, alert_def.id):
                        # Get latest metrics for budget
                        from app.services.metrics_service import MetricsService
                        metrics = await MetricsService.get_latest_metrics(db, project.id)

                        if metrics and metrics.budget_total and metrics.budget_consumed:
                            budget_percent = (metrics.budget_consumed / metrics.budget_total) * 100

                            if budget_percent >= 100:
                                template = await AlertService.get_template(db, alert_def.id, "initial")
                                if template:
                                    context = {
                                        "project_name": project.name,
                                        "budget_percent": round(budget_percent, 1),
                                        "budget_consumed": round(metrics.budget_consumed, 2),
                                        "budget_total": round(metrics.budget_total, 2),
                                    }
                                    message = AlertService.render_template(template, context)

                                    result = await SlackService.send_message(
                                        slack_config.bot_token_encrypted,
                                        slack_config.leadership_channel_id,
                                        message,
                                    )

                                    await AlertService.log_notification(
                                        db, project.id, alert_def.id,
                                        slack_config.leadership_channel_id, message,
                                        "sent" if result.get("ok") else "failed",
                                        metadata={"budget_percent": budget_percent},
                                    )

                                    if result.get("ok"):
                                        alerts_sent += 1

            # Check timeline at risk
            if "timeline_at_risk" in alert_defs:
                alert_def = alert_defs["timeline_at_risk"]

                if not await AlertService.is_silenced(db, project.id, alert_def.id):
                    if not await AlertService.was_notified_this_month(db, project.id, alert_def.id):
                        if project.end_date:
                            # Get metrics for velocity calculation
                            from app.services.metrics_service import MetricsService
                            metrics = await MetricsService.get_latest_metrics(db, project.id)

                            if metrics and metrics.velocity_issues_per_week:
                                weeks_remaining = (project.end_date - today).days / 7
                                remaining_issues = metrics.backlog_items or 0
                                velocity = metrics.velocity_issues_per_week

                                if velocity > 0 and weeks_remaining > 0:
                                    weeks_needed = remaining_issues / velocity

                                    if weeks_needed > weeks_remaining:
                                        template = await AlertService.get_template(db, alert_def.id, "initial")
                                        if template:
                                            context = {
                                                "project_name": project.name,
                                                "remaining_issues": remaining_issues,
                                                "weeks_remaining": round(weeks_remaining, 1),
                                                "velocity": round(velocity, 1),
                                            }
                                            message = AlertService.render_template(template, context)

                                            result = await SlackService.send_message(
                                                slack_config.bot_token_encrypted,
                                                slack_config.leadership_channel_id,
                                                message,
                                            )

                                            await AlertService.log_notification(
                                                db, project.id, alert_def.id,
                                                slack_config.leadership_channel_id, message,
                                                "sent" if result.get("ok") else "failed",
                                            )

                                            if result.get("ok"):
                                                alerts_sent += 1

            # Check project overdue
            if "project_overdue" in alert_defs:
                alert_def = alert_defs["project_overdue"]
                grace_days = alert_def.config_json.get("grace_days", 30)

                if not await AlertService.is_silenced(db, project.id, alert_def.id):
                    if not await AlertService.was_notified_this_month(db, project.id, alert_def.id):
                        if project.end_date:
                            overdue_threshold = project.end_date + timedelta(days=grace_days)

                            if today > overdue_threshold:
                                days_overdue = (today - project.end_date).days

                                template = await AlertService.get_template(db, alert_def.id, "initial")
                                if template:
                                    context = {
                                        "project_name": project.name,
                                        "days_overdue": days_overdue,
                                        "end_date": project.end_date.strftime("%Y-%m-%d"),
                                    }
                                    message = AlertService.render_template(template, context)

                                    result = await SlackService.send_message(
                                        slack_config.bot_token_encrypted,
                                        slack_config.leadership_channel_id,
                                        message,
                                    )

                                    await AlertService.log_notification(
                                        db, project.id, alert_def.id,
                                        slack_config.leadership_channel_id, message,
                                        "sent" if result.get("ok") else "failed",
                                        metadata={"days_overdue": days_overdue},
                                    )

                                    if result.get("ok"):
                                        alerts_sent += 1

        job_run.status = "success"
        job_run.projects_checked = projects_checked
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "projects_checked": projects_checked,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        job_run.status = "failed"
        job_run.error_message = str(e)
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_check_business_alerts_job.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/worker/check_business_alerts.py backend/tests/test_check_business_alerts_job.py
git commit -m "feat(worker): add business alerts check scheduled job"
```

---

### Task 11: Register Cron Jobs in Worker Settings

**Files:**
- Modify: `backend/app/worker/settings.py`

**Step 1: Update worker settings with cron jobs**

```python
# Add to backend/app/worker/settings.py
from arq.cron import cron

# Import cron job functions
from app.worker.check_dependabot import check_dependabot_alerts
from app.worker.check_business_alerts import check_business_alerts

# Add to WorkerSettings class:
cron_jobs = [
    cron(check_dependabot_alerts, hour=8, minute=0),
    cron(check_business_alerts, hour=9, minute=0),
]
```

**Step 2: Commit**

```bash
git add backend/app/worker/settings.py
git commit -m "feat(worker): register Dependabot and business alert cron jobs"
```

---

## Phase 4: API Endpoints

### Task 12: Create Slack Admin API Endpoints

**Files:**
- Create: `backend/app/api/slack_admin.py`
- Create: `backend/app/api/schemas/slack.py`
- Test: `backend/tests/test_slack_admin_api.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_slack_admin_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_slack_config():
    response = client.get("/api/admin/slack/config")
    assert response.status_code in [200, 404]

def test_list_channels_requires_config():
    response = client.get("/api/admin/slack/channels")
    assert response.status_code in [200, 400]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_slack_admin_api.py -v`
Expected: FAIL with 404 (route not found)

**Step 3: Create schemas**

```python
# backend/app/api/schemas/slack.py
"""Slack API schemas."""
from datetime import datetime
from pydantic import BaseModel, Field


class SlackConfigResponse(BaseModel):
    """Slack config response (token masked)."""
    id: int
    bot_token_configured: bool
    leadership_channel_id: str | None
    created_at: datetime
    updated_at: datetime


class SlackConfigUpdate(BaseModel):
    """Update Slack config."""
    bot_token: str | None = Field(None, description="Slack bot token (xoxb-...)")
    leadership_channel_id: str | None = Field(None, max_length=50)


class SlackChannel(BaseModel):
    """Slack channel info."""
    id: str
    name: str
    is_private: bool


class SlackTestResult(BaseModel):
    """Result of Slack connection test."""
    ok: bool
    team: str | None = None
    bot_id: str | None = None
    error: str | None = None


class AlertDefinitionResponse(BaseModel):
    """Alert definition response."""
    id: int
    name: str
    description: str | None
    category: str
    channel_type: str
    schedule: str
    is_enabled: bool
    config_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertDefinitionUpdate(BaseModel):
    """Update alert definition."""
    is_enabled: bool | None = None
    config_json: dict | None = None


class MessageTemplateResponse(BaseModel):
    """Message template response."""
    id: int
    alert_definition_id: int
    template_type: str
    message_template: str
    is_active: bool

    model_config = {"from_attributes": True}


class MessageTemplateUpdate(BaseModel):
    """Update message template."""
    message_template: str | None = None
    is_active: bool | None = None
```

**Step 4: Create API endpoints**

```python
# backend/app/api/slack_admin.py
"""Slack admin API endpoints."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    SlackChannel,
    SlackConfigResponse,
    SlackConfigUpdate,
    SlackTestResult,
)
from app.models.slack import (
    AlertDefinitionDB,
    MessageTemplateDB,
    SlackConfigDB,
)
from app.services.slack_service import SlackService

router = APIRouter(prefix="/admin/slack", tags=["slack-admin"])


@router.get("/config", response_model=SlackConfigResponse)
async def get_slack_config(db: DBSession) -> SlackConfigResponse:
    """Get Slack configuration (token masked)."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        # Create default config
        config = SlackConfigDB()
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return SlackConfigResponse(
        id=config.id,
        bot_token_configured=bool(config.bot_token_encrypted),
        leadership_channel_id=config.leadership_channel_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/config", response_model=SlackConfigResponse)
async def update_slack_config(
    update: SlackConfigUpdate,
    db: DBSession,
) -> SlackConfigResponse:
    """Update Slack configuration."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    config = result.scalar_one_or_none()

    if not config:
        config = SlackConfigDB()
        db.add(config)

    if update.bot_token is not None:
        config.bot_token_encrypted = update.bot_token
    if update.leadership_channel_id is not None:
        config.leadership_channel_id = update.leadership_channel_id

    await db.commit()
    await db.refresh(config)

    return SlackConfigResponse(
        id=config.id,
        bot_token_configured=bool(config.bot_token_encrypted),
        leadership_channel_id=config.leadership_channel_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/test", response_model=SlackTestResult)
async def test_slack_connection(db: DBSession) -> SlackTestResult:
    """Test Slack bot token."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    config = result.scalar_one_or_none()

    if not config or not config.bot_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack bot token not configured",
        )

    test_result = await SlackService.test_connection(config.bot_token_encrypted)

    return SlackTestResult(
        ok=test_result.get("ok", False),
        team=test_result.get("team"),
        bot_id=test_result.get("bot_id"),
        error=test_result.get("error"),
    )


@router.get("/channels", response_model=list[SlackChannel])
async def list_slack_channels(db: DBSession) -> list[SlackChannel]:
    """List available Slack channels."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    config = result.scalar_one_or_none()

    if not config or not config.bot_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack bot token not configured",
        )

    channels = await SlackService.list_channels(config.bot_token_encrypted)

    return [
        SlackChannel(
            id=ch["id"],
            name=ch["name"],
            is_private=ch.get("is_private", False),
        )
        for ch in channels
    ]


# Alert definitions endpoints
alerts_router = APIRouter(prefix="/admin/alerts", tags=["alerts-admin"])


@alerts_router.get("/", response_model=list[AlertDefinitionResponse])
async def list_alert_definitions(db: DBSession) -> list[AlertDefinitionResponse]:
    """List all alert definitions."""
    result = await db.execute(select(AlertDefinitionDB))
    return list(result.scalars().all())


@alerts_router.put("/{alert_id}", response_model=AlertDefinitionResponse)
async def update_alert_definition(
    alert_id: int,
    update: AlertDefinitionUpdate,
    db: DBSession,
) -> AlertDefinitionResponse:
    """Update an alert definition."""
    result = await db.execute(
        select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert definition not found",
        )

    if update.is_enabled is not None:
        alert.is_enabled = update.is_enabled
    if update.config_json is not None:
        alert.config_json = update.config_json

    await db.commit()
    await db.refresh(alert)
    return alert


@alerts_router.get("/{alert_id}/templates", response_model=list[MessageTemplateResponse])
async def get_alert_templates(
    alert_id: int,
    db: DBSession,
) -> list[MessageTemplateResponse]:
    """Get message templates for an alert."""
    result = await db.execute(
        select(MessageTemplateDB).where(
            MessageTemplateDB.alert_definition_id == alert_id
        )
    )
    return list(result.scalars().all())


# Templates endpoints
templates_router = APIRouter(prefix="/admin/templates", tags=["templates-admin"])


@templates_router.put("/{template_id}", response_model=MessageTemplateResponse)
async def update_message_template(
    template_id: int,
    update: MessageTemplateUpdate,
    db: DBSession,
) -> MessageTemplateResponse:
    """Update a message template."""
    result = await db.execute(
        select(MessageTemplateDB).where(MessageTemplateDB.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    if update.message_template is not None:
        template.message_template = update.message_template
    if update.is_active is not None:
        template.is_active = update.is_active

    await db.commit()
    await db.refresh(template)
    return template
```

**Step 5: Register routers in main.py**

Add to `backend/app/main.py`:
```python
from app.api.slack_admin import router as slack_router, alerts_router, templates_router

app.include_router(slack_router)
app.include_router(alerts_router)
app.include_router(templates_router)
```

**Step 6: Run tests**

Run: `cd backend && pytest tests/test_slack_admin_api.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/api/slack_admin.py backend/app/api/schemas/slack.py backend/app/main.py backend/tests/test_slack_admin_api.py
git commit -m "feat(api): add Slack admin endpoints"
```

---

## Phase 5: Remaining API & Frontend

### Task 13: Create Silences API

### Task 14: Create Notifications Log API

### Task 15: Create Scheduled Jobs API

### Task 16: Add slack_channel_id to Project Form (Frontend)

### Task 17: Create Notifications Admin Page (Frontend)

### Task 18: Add Scheduled Jobs Section to Jobs Page (Frontend)

---

## Summary

**Total Tasks:** 18

**Phase 1 (Database):** Tasks 1-5
**Phase 2 (Services):** Tasks 6-7
**Phase 3 (Jobs):** Tasks 8-11
**Phase 4 (API):** Tasks 12-15
**Phase 5 (Frontend):** Tasks 16-18

Each task follows TDD: write failing test → implement → verify → commit.
