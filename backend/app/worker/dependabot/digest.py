"""Dependabot Slack digest: one summary message per project, alert list in its thread."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.scorecard.services.collectors.dependabot import DependabotCollector
from app.worker.dependabot.shared import NO_CVE, REMINDER_DAYS, slack_send

logger = structlog.get_logger()

DEFAULT_SUMMARY_TEMPLATE = (
    ":rotating_light: *{project_name}* has {open_count} open high/critical "
    "vulnerabilities ({critical_count} critical, {high_count} high, {new_count} new)\n"
    "*Please, fix them ASAP.* <{alerts_url}|View in GitHub> · full list in the thread"
)

# Keeps each thread reply well under Slack's recommended 4000-char message size.
LINES_PER_REPLY = 20

SEVERITY_ORDER = {"critical": 0, "high": 1}
SEVERITY_EMOJI = {"critical": ":red_circle:", "high": ":large_orange_circle:"}


@dataclass(frozen=True)
class DigestItem:
    github_alert_id: int
    severity: str
    package_name: str
    cve_id: str
    manifest_path: str
    days_open: int
    is_new: bool


def is_reminder_due(
    tracked: DependabotAlertTrackedDB,
    current_alert_ids: set[int],
    now: datetime,
) -> bool:
    """True iff this tracked alert is unresolved, still open in GitHub, and past its cadence."""
    if tracked.resolved_at:
        return False
    if tracked.github_alert_id not in current_alert_ids:
        return False

    severity = (tracked.severity or "").lower()
    reminder_days = REMINDER_DAYS.get(severity)
    if not reminder_days:
        return False

    if tracked.last_notified_at:
        next_reminder = tracked.last_notified_at + timedelta(days=reminder_days)
        if now < next_reminder:
            return False

    return True


def build_digest_items(
    current_alerts: list[dict],
    open_tracked: dict[int, DependabotAlertTrackedDB],
    now: datetime,
) -> list[DigestItem]:
    """Every open alert, critical first, then new, then oldest."""
    items = []
    for alert in current_alerts:
        info = DependabotCollector.extract_alert_info(alert)
        tracked = open_tracked.get(info["github_alert_id"])
        first_seen = tracked.first_seen_at if tracked else None
        items.append(
            DigestItem(
                github_alert_id=info["github_alert_id"],
                severity=(info["severity"] or "unknown").lower(),
                package_name=info["package_name"] or "Unknown package",
                cve_id=info["cve_id"] or NO_CVE,
                manifest_path=info.get("manifest_path") or "",
                days_open=(now - first_seen).days if first_seen else 0,
                is_new=tracked is None,
            )
        )
    items.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), not i.is_new, -i.days_open))
    return items


def _code(value: str) -> str:
    # Backticks are the only character that can break out of a code span.
    return f"`{value.replace('`', '')}`"


def format_item_line(repo: str, item: DigestItem) -> str:
    url = f"https://github.com/{repo}/security/dependabot/{item.github_alert_id}"
    emoji = SEVERITY_EMOJI.get(item.severity, ":white_circle:")
    age = ":new: new" if item.is_new else f"open {item.days_open}d"
    parts = [f"{emoji} *{item.severity}* {_code(item.package_name)}", item.cve_id]
    if item.manifest_path:
        parts.append(_code(item.manifest_path))
    parts += [age, f"<{url}|#{item.github_alert_id}>"]
    return " · ".join(parts)


def build_summary(template: str, project: ProjectDB, items: list[DigestItem]) -> str:
    context = {
        "project_name": project.name,
        "open_count": len(items),
        "critical_count": sum(1 for i in items if i.severity == "critical"),
        "high_count": sum(1 for i in items if i.severity == "high"),
        "new_count": sum(1 for i in items if i.is_new),
    }
    # The URL is spliced after rendering: render_template escapes "_" and "|",
    # which would break the link for repos with those characters in their name.
    alerts_url = f"https://github.com/{project.github_repo}/security/dependabot"
    rendered = AlertService.render_template(template, context)
    return rendered.replace("{alerts_url}", alerts_url)


async def send_digest(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    tracked_alerts: list[DependabotAlertTrackedDB],
    current_alerts: list[dict],
) -> int:
    """Post the digest when an alert is new or a reminder is due.

    The thread always lists every open alert, so each digest is a complete
    snapshot and all listed alerts restart their reminder cadence. Returns the
    number of alerts reported.
    """
    now = datetime.now(UTC)
    current_alert_ids = {alert["number"] for alert in current_alerts}
    open_tracked = {t.github_alert_id: t for t in tracked_alerts if not t.resolved_at}

    has_new = bool(current_alert_ids - open_tracked.keys())
    has_due = any(is_reminder_due(t, current_alert_ids, now) for t in open_tracked.values())
    if not (has_new or has_due):
        return 0

    items = build_digest_items(current_alerts, open_tracked, now)
    template = (
        await AlertService.get_template(db, alert_definition.id, "initial")
        or DEFAULT_SUMMARY_TEMPLATE
    )
    summary = build_summary(template, project, items)
    response = await slack_send(bot_token, project.slack_channel_id, summary)

    await AlertService.log_notification(
        db=db,
        project_id=project.id,
        alert_definition_id=alert_definition.id,
        channel_id=project.slack_channel_id,
        message=summary,
        status="sent" if response.get("ok") else "failed",
        error_message=None if response.get("ok") else response.get("error"),
        metadata={
            "open_count": len(items),
            "new_alert_ids": [i.github_alert_id for i in items if i.is_new],
        },
    )
    if not response.get("ok"):
        await db.commit()
        return 0

    lines = [format_item_line(project.github_repo, item) for item in items]
    for start in range(0, len(lines), LINES_PER_REPLY):
        reply = await slack_send(
            bot_token,
            project.slack_channel_id,
            "\n".join(lines[start : start + LINES_PER_REPLY]),
            thread_ts=response.get("ts"),
        )
        if not reply.get("ok"):
            logger.warning(
                "dependabot_thread_reply_failed",
                project=project.name,
                error=reply.get("error"),
            )

    _record_notified(db, project, items, open_tracked, current_alerts, now)
    await db.commit()

    logger.info(
        "dependabot_digest_sent",
        project=project.name,
        open_count=len(items),
        new_count=sum(1 for i in items if i.is_new),
    )
    return len(items)


def _record_notified(
    db: AsyncSession,
    project: ProjectDB,
    items: list[DigestItem],
    open_tracked: dict[int, DependabotAlertTrackedDB],
    current_alerts: list[dict],
    now: datetime,
) -> None:
    for tracked in open_tracked.values():
        tracked.last_notified_at = now

    new_ids = {i.github_alert_id for i in items if i.is_new}
    for alert in current_alerts:
        info = DependabotCollector.extract_alert_info(alert)
        if info["github_alert_id"] not in new_ids:
            continue
        db.add(
            DependabotAlertTrackedDB(
                project_id=project.id,
                github_alert_id=info["github_alert_id"],
                package_name=info["package_name"],
                severity=info["severity"],
                cve_id=info["cve_id"],
                manifest_path=info.get("manifest_path"),
                last_notified_at=now,
            )
        )
