"""Diff engine for comparing access snapshots."""

from typing import Any


def compute_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
    domain: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    changes.extend(_diff_users(current_data, previous_data))
    changes.extend(_diff_admins(current_data, previous_data))

    return changes


def _diff_users(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_emails = {u["email"]: u for u in current["users"]}
    previous_emails = {u["email"]: u for u in previous["users"]}
    changes: list[dict[str, Any]] = []

    for email in current_emails.keys() - previous_emails.keys():
        u = current_emails[email]
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": u.get("name", ""),
            "change_type": "new_user",
            "previous_value": None,
            "current_value": {"email": email, "name": u.get("name", "")},
        })

    for email in previous_emails.keys() - current_emails.keys():
        u = previous_emails[email]
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": u.get("name", ""),
            "change_type": "removed_user",
            "previous_value": {"email": email, "name": u.get("name", "")},
            "current_value": None,
        })

    return changes


def _diff_admins(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_admin_emails = {
        ra["user_email"] for ra in current["role_assignments"]
    }
    previous_admin_emails = {
        ra["user_email"] for ra in previous["role_assignments"]
    }

    current_users = {u["email"]: u for u in current["users"]}
    previous_users = {u["email"]: u for u in previous["users"]}
    all_users = {**previous_users, **current_users}
    changes: list[dict[str, Any]] = []

    for email in current_admin_emails - previous_admin_emails:
        user = all_users.get(email, {})
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": user.get("name", ""),
            "change_type": "role_change",
            "previous_value": {"is_admin": False},
            "current_value": {"is_admin": True},
        })

    for email in previous_admin_emails - current_admin_emails:
        user = all_users.get(email, {})
        changes.append({
            "subject_type": "user",
            "subject_id": email,
            "subject_label": user.get("name", ""),
            "change_type": "role_change",
            "previous_value": {"is_admin": True},
            "current_value": {"is_admin": False},
        })

    return changes
