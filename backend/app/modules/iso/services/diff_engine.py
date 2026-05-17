"""Diff engine for comparing access snapshots."""

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.services.diff_github import compute_github_diff
from app.modules.iso.services.diff_jira import compute_jira_diff


def compute_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
    domain: str,
    provider: str = "google_workspace",
) -> list[dict[str, Any]]:
    if provider == "github":
        return compute_github_diff(current_data, previous_data)

    if provider == "jira":
        return compute_jira_diff(current_data, previous_data)

    changes: list[dict[str, Any]] = []

    changes.extend(_diff_users(current_data, previous_data))
    changes.extend(_diff_admins(current_data, previous_data))
    changes.extend(_diff_group_members(current_data, previous_data))
    changes.extend(_diff_externals(current_data, previous_data, domain))

    return changes


def _diff_users(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_emails = {u["email"]: u for u in current["users"]}
    previous_emails = {u["email"]: u for u in previous["users"]}
    changes: list[dict[str, Any]] = []

    for email in current_emails.keys() - previous_emails.keys():
        u = current_emails[email]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": email,
                "subject_label": u.get("name", ""),
                "change_type": "new_user",
                "previous_value": None,
                "current_value": {"email": email, "name": u.get("name", "")},
            }
        )

    for email in previous_emails.keys() - current_emails.keys():
        u = previous_emails[email]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": email,
                "subject_label": u.get("name", ""),
                "change_type": "removed_user",
                "previous_value": {"email": email, "name": u.get("name", "")},
                "current_value": None,
            }
        )

    return changes


def _diff_admins(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_admin_emails = {ra["user_email"] for ra in current["role_assignments"]}
    previous_admin_emails = {ra["user_email"] for ra in previous["role_assignments"]}

    current_users = {u["email"]: u for u in current["users"]}
    previous_users = {u["email"]: u for u in previous["users"]}
    all_users = {**previous_users, **current_users}
    changes: list[dict[str, Any]] = []

    for email in current_admin_emails - previous_admin_emails:
        user = all_users.get(email, {})
        changes.append(
            {
                "subject_type": "user",
                "subject_id": email,
                "subject_label": user.get("name", ""),
                "change_type": "role_change",
                "previous_value": {"is_admin": False},
                "current_value": {"is_admin": True},
            }
        )

    for email in previous_admin_emails - current_admin_emails:
        user = all_users.get(email, {})
        changes.append(
            {
                "subject_type": "user",
                "subject_id": email,
                "subject_label": user.get("name", ""),
                "change_type": "role_change",
                "previous_value": {"is_admin": True},
                "current_value": {"is_admin": False},
            }
        )

    return changes


def _diff_group_members(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})
    current_groups = {g["email"]: g for g in current.get("groups", [])}
    all_group_emails = set(current_members.keys()) | set(previous_members.keys())
    changes: list[dict[str, Any]] = []

    for group_email in all_group_emails:
        curr_emails = {m["email"] for m in current_members.get(group_email, [])}
        prev_emails = {m["email"] for m in previous_members.get(group_email, [])}
        added = curr_emails - prev_emails
        removed = prev_emails - curr_emails

        if added or removed:
            group = current_groups.get(group_email, {})
            changes.append(
                {
                    "subject_type": "group",
                    "subject_id": group_email,
                    "subject_label": group.get("name", ""),
                    "change_type": "group_membership_change",
                    "previous_value": {"members": sorted(prev_emails)},
                    "current_value": {
                        "added": sorted(added),
                        "removed": sorted(removed),
                    },
                }
            )

    return changes


def _diff_externals(
    current: dict[str, Any],
    previous: dict[str, Any],
    domain: str,
) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})
    current_groups = {g["email"]: g for g in current.get("groups", [])}
    changes: list[dict[str, Any]] = []

    for group_email, members in current_members.items():
        curr_external = {
            m["email"] for m in members if m.get("email") and not m["email"].endswith(f"@{domain}")
        }
        prev_external = {
            m["email"]
            for m in previous_members.get(group_email, [])
            if m.get("email") and not m["email"].endswith(f"@{domain}")
        }
        new_external = curr_external - prev_external

        if new_external:
            group = current_groups.get(group_email, {})
            changes.append(
                {
                    "subject_type": "group",
                    "subject_id": group_email,
                    "subject_label": group.get("name", ""),
                    "change_type": "new_external",
                    "previous_value": None,
                    "current_value": {"external_added": sorted(new_external)},
                }
            )

    return changes


def build_diff_summary(changes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(c["change_type"] for c in changes)
    summary: dict[str, Any] = {
        "total_changes": len(changes),
        "new_user": counts.get("new_user", 0),
        "removed_user": counts.get("removed_user", 0),
        "role_change": counts.get("role_change", 0),
        "new_external": counts.get("new_external", 0),
        "group_membership_change": counts.get("group_membership_change", 0),
    }
    if counts.get("removed_external", 0):
        summary["removed_external"] = counts["removed_external"]
    return summary


async def create_review_actions(
    db: AsyncSession,
    review_id: UUID,
    changes: list[dict[str, Any]],
) -> None:
    for change in changes:
        action = AccessReviewActionDB(
            review_id=review_id,
            subject_type=change["subject_type"],
            subject_id=change["subject_id"],
            subject_label=change.get("subject_label"),
            change_type=change["change_type"],
            previous_value=change.get("previous_value"),
            current_value=change.get("current_value"),
        )
        db.add(action)
    await db.flush()
