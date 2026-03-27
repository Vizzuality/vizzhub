"""Public interface for the notifications module.

Other modules should import from here, never from notifications internals.
"""

from app.modules.notifications.api.schemas.slack import SlackChannel, SlackTestResult
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSilenceDB,
    DependabotAlertTrackedDB,
    MessageTemplateDB,
    ScheduledJobRunDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService

__all__ = [
    "AlertDefinitionDB",
    "AlertNotificationDB",
    "AlertSilenceDB",
    "AlertService",
    "DependabotAlertTrackedDB",
    "MessageTemplateDB",
    "ScheduledJobRunDB",
    "SlackChannel",
    "SlackService",
    "SlackTestResult",
]
