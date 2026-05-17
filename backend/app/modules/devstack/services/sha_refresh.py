"""Refresh catalog entry metadata (GitHub SHAs + npm versions)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import STALE_AFTER
from app.modules.devstack.services.github_sha import (
    fetch_github_content,
    fetch_github_sha,
)
from app.modules.devstack.services.npm_security import fetch_npm_advisories
from app.modules.devstack.services.npm_version import (
    fetch_npm_latest_version,  # kept for backward compat
    fetch_npm_package_info,
)
from app.modules.notifications.public import ScheduledJobRunDB, SlackService
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel

logger = structlog.get_logger()

JOB_NAME = "refresh_devstack_sources"


def _parse_frontmatter(content: str, *, name: str) -> dict:
    """Extract the YAML frontmatter block from a markdown file.

    Returns an empty dict on any failure but logs the failure mode so the
    operator can distinguish a stub skill from a malformed one (audit #13).
    """
    if not content.startswith("---"):
        logger.warning("devstack_frontmatter_missing_opening", name=name)
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        logger.warning("devstack_frontmatter_missing_closing", name=name)
        return {}
    try:
        parsed = yaml.safe_load(content[3:end])
    except yaml.YAMLError as exc:
        logger.warning("devstack_frontmatter_parse_failed", name=name, error=str(exc))
        return {}
    if not isinstance(parsed, dict):
        logger.warning("devstack_frontmatter_not_a_dict", name=name)
        return {}
    return parsed


async def _sync_github_frontmatter(
    entry: DevstackEntryDB, github_token: str | None
) -> None:
    """Pull `description` (and `name`) from the skill/command/agent frontmatter."""
    content = await fetch_github_content(entry.url, github_token)
    if content is None:
        logger.warning("devstack_content_fetch_failed_for_frontmatter", name=entry.name)
        return
    fm = _parse_frontmatter(content, name=entry.name)
    new_description = fm.get("description")
    if isinstance(new_description, str) and new_description != entry.description:
        entry.description = new_description
    new_name = fm.get("name")
    if isinstance(new_name, str) and new_name != entry.name:
        entry.name = new_name


async def _refresh_github_entry(
    entry: DevstackEntryDB, github_token: str | None
) -> str:
    """Return 'updated' | 'unchanged' | 'failed' for one github entry."""
    new_sha = await fetch_github_sha(entry.url, github_token)
    if new_sha is None:
        return "failed"
    entry.last_fetch_ok_at = datetime.now(timezone.utc)
    if new_sha != entry.github_sha:
        entry.github_sha = new_sha
        await _sync_github_frontmatter(entry, github_token)
        return "updated"
    return "unchanged"


def _apply_npm_deprecation(entry: DevstackEntryDB, info: dict) -> bool:
    """Sync version + deprecation from npm info. Return True if anything changed."""
    changed = False
    if info["version"] != entry.latest_package_version:
        entry.latest_package_version = info["version"]
        changed = True
    new_message = info["deprecation_message"]
    new_deprecated = new_message is not None
    if (
        new_deprecated != entry.deprecated
        or new_message != entry.deprecation_message
    ):
        entry.deprecated = new_deprecated
        entry.deprecation_message = new_message
        changed = True
    return changed


async def _refresh_npm_advisories(
    entry: DevstackEntryDB, info: dict, github_token: str | None
) -> bool:
    """Fetch + persist advisories for one npm entry. Return True if payload changed."""
    version_to_check = entry.package_version or info["version"]
    advisories = await fetch_npm_advisories(
        entry.package, version_to_check, github_token
    )
    if advisories is None:
        return False
    entry.vulnerabilities_checked_at = datetime.now(timezone.utc)
    if advisories != entry.vulnerabilities:
        entry.vulnerabilities = advisories
        return True
    return False


async def _refresh_npm_entry(
    entry: DevstackEntryDB, github_token: str | None
) -> str:
    """Return 'updated' | 'unchanged' | 'failed' for one npm entry."""
    info = await fetch_npm_package_info(entry.package)
    if info is None:
        return "failed"
    entry.last_fetch_ok_at = datetime.now(timezone.utc)
    changed = _apply_npm_deprecation(entry, info)
    if await _refresh_npm_advisories(entry, info, github_token):
        changed = True
    return "updated" if changed else "unchanged"


async def _refresh_one_entry(
    entry: DevstackEntryDB, github_token: str | None
) -> str | None:
    """Refresh a single entry. Returns its status, or None when skipped."""
    if entry.install_method == "github" and entry.url:
        return await _refresh_github_entry(entry, github_token)
    if entry.install_method == "npm" and entry.package:
        return await _refresh_npm_entry(entry, github_token)
    # claude_plugin: skipped (no auto-tracking).
    return None


def _is_entry_stale(entry: DevstackEntryDB, now: datetime) -> bool:
    """Required entry has gone too long without a successful fetch."""
    if not entry.required or entry.install_method == "claude_plugin":
        return False
    if entry.last_fetch_ok_at is None:
        return True
    return (now - entry.last_fetch_ok_at) > STALE_AFTER


async def refresh_all_sources(db: AsyncSession) -> dict[str, int | list[str] | bool]:
    """Refresh github_sha and latest_package_version for all active entries.

    - github entries: refetch blob SHA
    - npm entries: refetch latest published version + deprecation + advisories
    - claude_plugin entries: skipped (no auto-tracking)

    Returns: {total, updated, unchanged, failed, partial_failure, required_failures}.
    `required_failures` is the list of names of failed entries flagged
    `required: true` — surfaced separately so callers can escalate (audit #13).
    """
    result = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()
    github_token = await IntegrationTokenService.get_token(db, "github")

    counters: dict[str, int] = {"updated": 0, "unchanged": 0, "failed": 0}
    required_failures: list[str] = []
    processed = 0

    for entry in entries:
        status = await _refresh_one_entry(entry, github_token)
        if status is None:
            continue
        processed += 1
        counters[status] += 1
        if status == "failed" and entry.required:
            required_failures.append(entry.name)

    # `required_stale` is the persistence dimension: a required entry that
    # hasn't refreshed inside STALE_AFTER, regardless of whether THIS run
    # succeeded or failed. A flaky GitHub outage that succeeded today but
    # was stale yesterday-and-before shows up here, even though
    # `required_failures` for this run is empty.
    now = datetime.now(timezone.utc)
    required_stale = sorted(e.name for e in entries if _is_entry_stale(e, now))

    # `last_fetch_ok_at` advances on every non-failed entry, so commit even
    # when nothing else changed — otherwise the freshness signal would
    # itself be stale.
    await db.commit()

    summary: dict[str, int | list[str] | bool] = {
        "total": processed,
        "partial_failure": counters["failed"] > 0,
        "required_failures": required_failures,
        "required_stale": required_stale,
        **counters,
    }
    if required_failures or required_stale:
        logger.error(
            "devstack_required_entry_sync_failed",
            required_failures=required_failures,
            required_stale=required_stale,
            total=processed,
            failed=counters["failed"],
            updated=counters["updated"],
            unchanged=counters["unchanged"],
        )
    elif counters["failed"] > 0:
        logger.warning("devstack_sources_refresh_partial_failure", **summary)
    else:
        logger.info("devstack_sources_refresh_completed", **summary)
    return summary


async def _alert_required_failures(db: AsyncSession, names: list[str]) -> None:
    """Slack-notify leadership when a `required: true` catalog entry fails to refresh."""
    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            logger.warning(
                "devstack_required_failure_slack_not_configured",
                required_failures=names,
            )
            return
        channel_id = await get_slack_leadership_channel(db)
        if not channel_id:
            logger.warning(
                "devstack_required_failure_channel_not_configured",
                required_failures=names,
            )
            return
        message = (
            ":rotating_light: *DevStack — Required entries failed to refresh*\n"
            f"Entries: {', '.join(f'`{n}`' for n in names)}\n"
            "Required catalog items are out of date. "
            "Investigate GitHub access / npm registry availability."
        )
        await SlackService.send_message(bot_token, channel_id, message)
        logger.info(
            "devstack_required_failure_alert_sent", required_failures=names
        )
    except Exception:
        logger.exception(
            "devstack_required_failure_alert_send_failed",
            required_failures=names,
        )


async def refresh_all_sources_tracked(db: AsyncSession) -> dict[str, int | list[str] | bool]:
    """Run refresh_all_sources, record the run, escalate required-entry failures."""
    job_run = ScheduledJobRunDB(job_name=JOB_NAME, status="running")
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        result = await refresh_all_sources(db)
        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.projects_checked = result["total"]
        job_run.alerts_sent = result["updated"]
        await db.commit()

        required_failures = result.get("required_failures") or []
        if required_failures:
            await _alert_required_failures(db, list(required_failures))

        return result
    except Exception as e:
        job_run.status = "error"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.error_message = str(e)
        await db.commit()
        raise
