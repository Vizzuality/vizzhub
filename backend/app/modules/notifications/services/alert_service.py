"""Alert management service."""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import (
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
)

# Slack mrkdwn metacharacters: bold *, italic _, code `, blockquote >, link <…|…>.
# Escape with backslash so user-controlled strings can't open formatting we
# didn't write ourselves.
# Ref: https://api.slack.com/reference/surfaces/formatting#escaping
_SLACK_MRKDWN_META = re.compile(r"([*_`>|<])")


def markdown_escape(value: Any) -> str:
    """Escape Slack mrkdwn metacharacters in a value.

    Stringifies the value then prefixes every mrkdwn metacharacter
    (``*``, ``_``, `` ` ``, ``>``, ``|``, ``<``) with a backslash so
    that interpolated text from untrusted sources cannot inject Slack
    formatting (bold, italic, code, blockquote, links).
    """
    return _SLACK_MRKDWN_META.sub(r"\\\1", str(value))


class AlertService:
    """Service for managing alerts."""

    @staticmethod
    def render_template(template: str, context: dict[str, Any]) -> str:
        """Render a message template with context values.

        Replaces {placeholder} patterns in the template with corresponding
        values from the context dictionary. Missing placeholders are preserved.
        Interpolated values are escaped for Slack mrkdwn so that
        untrusted sources (e.g. Jira-supplied fields) cannot inject
        bold/italic/code/link formatting.

        Args:
            template: Message template with {placeholder} patterns.
            context: Dictionary of values to substitute.

        Returns:
            Rendered template string.
        """

        def replace_placeholder(match: re.Match) -> str:
            key = match.group(1)
            if key not in context:
                return match.group(0)
            return markdown_escape(context[key])

        result = re.sub(r"\{(\w+)\}", replace_placeholder, template)
        # Convert literal \n to actual newlines
        return result.replace("\\n", "\n")

    @staticmethod
    async def is_silenced(
        db: AsyncSession,
        project_id: UUID,
        alert_definition_id: int | None = None,
    ) -> bool:
        """Check if alerts are silenced for a project.

        A project is considered silenced if:
        - There's a global silence (alert_definition_id is null) that hasn't expired
        - There's a specific silence for the given alert that hasn't expired
        - Silence is indefinite (silenced_until is null)

        Args:
            db: Database session.
            project_id: Project UUID to check.
            alert_definition_id: Optional specific alert to check.

        Returns:
            True if alerts are silenced, False otherwise.
        """
        now = datetime.now(UTC)

        query = select(AlertSilenceDB).where(
            AlertSilenceDB.project_id == project_id,
            (AlertSilenceDB.alert_definition_id.is_(None))
            | (AlertSilenceDB.alert_definition_id == alert_definition_id),
            (AlertSilenceDB.silenced_until.is_(None)) | (AlertSilenceDB.silenced_until > now),
        )

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def was_notified_this_month(
        db: AsyncSession,
        project_id: UUID,
        alert_definition_id: int,
    ) -> bool:
        """Check if this alert was already sent this month for this project.

        Used for monthly throttling of alerts to prevent notification fatigue.

        Args:
            db: Database session.
            project_id: Project UUID to check.
            alert_definition_id: Alert definition ID to check.

        Returns:
            True if a successful notification was sent this month, False otherwise.
        """
        now = datetime.now(UTC)
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
        """Get the message template for an alert.

        Args:
            db: Database session.
            alert_definition_id: Alert definition ID.
            template_type: Type of template (initial, reminder, escalation).

        Returns:
            Template string if found, None otherwise.
        """
        query = select(MessageTemplateDB).where(
            MessageTemplateDB.alert_definition_id == alert_definition_id,
            MessageTemplateDB.template_type == template_type,
            MessageTemplateDB.is_active.is_(True),
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
        """Log a sent notification.

        Creates a record of the notification attempt for audit and throttling.

        Args:
            db: Database session.
            project_id: Project UUID.
            alert_definition_id: Alert definition ID.
            channel_id: Slack channel ID the message was sent to.
            message: The message content that was sent.
            status: Status of the notification (sent, failed).
            error_message: Error message if the notification failed.
            metadata: Additional metadata about the notification.

        Returns:
            The created AlertNotificationDB record.
        """
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
