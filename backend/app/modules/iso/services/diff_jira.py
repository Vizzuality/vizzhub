"""Jira-specific diff functions for ISO access snapshots."""

from typing import Any

ADMIN_GROUPS = {"jira-administrators", "site-admins"}


def compute_jira_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    changes.extend(_diff_users(current_data, previous_data))
    changes.extend(_diff_admins(current_data, previous_data))
    changes.extend(_diff_externals(current_data, previous_data))
    changes.extend(_diff_group_members(current_data, previous_data))

    return changes


def _diff_users(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_users = {
        u["account_id"]: u for u in current.get("users", []) if not u.get("is_external", False)
    }
    previous_users = {
        u["account_id"]: u for u in previous.get("users", []) if not u.get("is_external", False)
    }
    changes: list[dict[str, Any]] = []

    for account_id in current_users.keys() - previous_users.keys():
        u = current_users[account_id]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": u.get("display_name") or account_id,
                "change_type": "new_user",
                "previous_value": None,
                "current_value": {"account_id": account_id},
            }
        )

    for account_id in previous_users.keys() - current_users.keys():
        u = previous_users[account_id]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": u.get("display_name") or account_id,
                "change_type": "removed_user",
                "previous_value": {"account_id": account_id},
                "current_value": None,
            }
        )

    return changes


def _diff_admins(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})

    current_admin_ids: set[str] = set()
    for group_name in ADMIN_GROUPS:
        for m in current_members.get(group_name, []):
            current_admin_ids.add(m["account_id"])

    previous_admin_ids: set[str] = set()
    for group_name in ADMIN_GROUPS:
        for m in previous_members.get(group_name, []):
            previous_admin_ids.add(m["account_id"])

    current_users = {u["account_id"]: u for u in current.get("users", [])}
    previous_users = {u["account_id"]: u for u in previous.get("users", [])}
    all_users = {**previous_users, **current_users}
    changes: list[dict[str, Any]] = []

    for account_id in current_admin_ids - previous_admin_ids:
        user = all_users.get(account_id, {})
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": user.get("display_name") or account_id,
                "change_type": "role_change",
                "previous_value": {"is_admin": False},
                "current_value": {"is_admin": True},
            }
        )

    for account_id in previous_admin_ids - current_admin_ids:
        user = all_users.get(account_id, {})
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": user.get("display_name") or account_id,
                "change_type": "role_change",
                "previous_value": {"is_admin": True},
                "current_value": {"is_admin": False},
            }
        )

    return changes


def _diff_externals(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_externals = {
        u["account_id"]: u for u in current.get("users", []) if u.get("is_external", False)
    }
    previous_externals = {
        u["account_id"]: u for u in previous.get("users", []) if u.get("is_external", False)
    }
    changes: list[dict[str, Any]] = []

    for account_id in current_externals.keys() - previous_externals.keys():
        u = current_externals[account_id]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": u.get("display_name") or account_id,
                "change_type": "new_external",
                "previous_value": None,
                "current_value": {"account_id": account_id},
            }
        )

    for account_id in previous_externals.keys() - current_externals.keys():
        u = previous_externals[account_id]
        changes.append(
            {
                "subject_type": "user",
                "subject_id": account_id,
                "subject_label": u.get("display_name") or account_id,
                "change_type": "removed_external",
                "previous_value": {"account_id": account_id},
                "current_value": None,
            }
        )

    return changes


def _diff_group_members(current: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    current_members = current.get("group_members", {})
    previous_members = previous.get("group_members", {})
    current_groups = {g["name"]: g for g in current.get("groups", [])}
    all_names = set(current_members.keys()) | set(previous_members.keys())
    changes: list[dict[str, Any]] = []

    for group_name in all_names:
        curr_ids = {m["account_id"] for m in current_members.get(group_name, [])}
        prev_ids = {m["account_id"] for m in previous_members.get(group_name, [])}
        added = curr_ids - prev_ids
        removed = prev_ids - curr_ids

        if added or removed:
            changes.append(
                {
                    "subject_type": "group",
                    "subject_id": group_name,
                    "subject_label": current_groups.get(group_name, {}).get("name", group_name),
                    "change_type": "group_membership_change",
                    "previous_value": {"members": sorted(prev_ids)},
                    "current_value": {
                        "added": sorted(added),
                        "removed": sorted(removed),
                    },
                }
            )

    return changes
