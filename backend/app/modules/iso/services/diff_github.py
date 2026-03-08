"""GitHub-specific diff functions for ISO access snapshots."""

from typing import Any


def compute_github_diff(
    current_data: dict[str, Any],
    previous_data: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    changes.extend(_diff_members(current_data, previous_data))
    changes.extend(_diff_member_roles(current_data, previous_data))
    changes.extend(_diff_outside_collaborators(current_data, previous_data))
    changes.extend(_diff_team_members(current_data, previous_data))

    return changes


def _diff_members(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_logins = {m["login"]: m for m in current.get("members", [])}
    previous_logins = {m["login"]: m for m in previous.get("members", [])}
    changes: list[dict[str, Any]] = []

    for login in current_logins.keys() - previous_logins.keys():
        m = current_logins[login]
        changes.append({
            "subject_type": "user",
            "subject_id": login,
            "subject_label": m.get("name") or login,
            "change_type": "new_user",
            "previous_value": None,
            "current_value": {"login": login, "role": m["role"]},
        })

    for login in previous_logins.keys() - current_logins.keys():
        m = previous_logins[login]
        changes.append({
            "subject_type": "user",
            "subject_id": login,
            "subject_label": m.get("name") or login,
            "change_type": "removed_user",
            "previous_value": {"login": login, "role": m["role"]},
            "current_value": None,
        })

    return changes


def _diff_member_roles(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_members = {m["login"]: m for m in current.get("members", [])}
    previous_members = {m["login"]: m for m in previous.get("members", [])}
    changes: list[dict[str, Any]] = []

    for login in current_members.keys() & previous_members.keys():
        curr_role = current_members[login]["role"]
        prev_role = previous_members[login]["role"]
        if curr_role != prev_role:
            m = current_members[login]
            changes.append({
                "subject_type": "user",
                "subject_id": login,
                "subject_label": m.get("name") or login,
                "change_type": "role_change",
                "previous_value": {"role": prev_role},
                "current_value": {"role": curr_role},
            })

    return changes


def _diff_outside_collaborators(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_logins = {
        c["login"]: c for c in current.get("outside_collaborators", [])
    }
    previous_logins = {
        c["login"]: c for c in previous.get("outside_collaborators", [])
    }
    changes: list[dict[str, Any]] = []

    for login in current_logins.keys() - previous_logins.keys():
        c = current_logins[login]
        changes.append({
            "subject_type": "user",
            "subject_id": login,
            "subject_label": c.get("name") or login,
            "change_type": "new_external",
            "previous_value": None,
            "current_value": {"login": login},
        })

    for login in previous_logins.keys() - current_logins.keys():
        c = previous_logins[login]
        changes.append({
            "subject_type": "user",
            "subject_id": login,
            "subject_label": c.get("name") or login,
            "change_type": "removed_external",
            "previous_value": {"login": login},
            "current_value": None,
        })

    return changes


def _diff_team_members(
    current: dict[str, Any], previous: dict[str, Any]
) -> list[dict[str, Any]]:
    current_teams = current.get("team_members", {})
    previous_teams = previous.get("team_members", {})
    current_team_info = {t["slug"]: t for t in current.get("teams", [])}
    all_slugs = set(current_teams.keys()) | set(previous_teams.keys())
    changes: list[dict[str, Any]] = []

    for slug in all_slugs:
        curr_logins = {m["login"] for m in current_teams.get(slug, [])}
        prev_logins = {m["login"] for m in previous_teams.get(slug, [])}
        added = curr_logins - prev_logins
        removed = prev_logins - curr_logins

        if added or removed:
            team = current_team_info.get(slug, {})
            changes.append({
                "subject_type": "group",
                "subject_id": slug,
                "subject_label": team.get("name", slug),
                "change_type": "group_membership_change",
                "previous_value": {"members": sorted(prev_logins)},
                "current_value": {
                    "added": sorted(added),
                    "removed": sorted(removed),
                },
            })

    return changes
