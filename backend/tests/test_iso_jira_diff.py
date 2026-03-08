"""Tests for Jira-specific ISO diff engine."""

from app.modules.iso.services.diff_jira import compute_jira_diff
from app.modules.iso.services.diff_engine import build_diff_summary, compute_diff


def _empty_jira_data() -> dict:
    return {"users": [], "groups": [], "group_members": {}}


class TestUserDiff:
    def test_diff_users_new(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
            {"account_id": "abc2", "display_name": "Bob", "is_external": False},
        ]
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]

        changes = compute_jira_diff(current, previous)

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 1
        assert new_users[0]["subject_id"] == "abc2"
        assert new_users[0]["subject_type"] == "user"
        assert new_users[0]["subject_label"] == "Bob"
        assert new_users[0]["current_value"] == {"account_id": "abc2"}
        assert new_users[0]["previous_value"] is None

    def test_diff_users_removed(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
            {"account_id": "abc2", "display_name": "Bob", "is_external": False},
        ]

        changes = compute_jira_diff(current, previous)

        removed = [c for c in changes if c["change_type"] == "removed_user"]
        assert len(removed) == 1
        assert removed[0]["subject_id"] == "abc2"
        assert removed[0]["previous_value"] == {"account_id": "abc2"}
        assert removed[0]["current_value"] is None

    def test_diff_users_no_changes(self) -> None:
        data = _empty_jira_data()
        data["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
            {"account_id": "abc2", "display_name": "Bob", "is_external": False},
        ]

        changes = compute_jira_diff(data, data)

        user_changes = [
            c for c in changes if c["change_type"] in ("new_user", "removed_user")
        ]
        assert len(user_changes) == 0

    def test_diff_users_skips_externals(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
            {"account_id": "ext1", "display_name": "Vendor", "is_external": True},
        ]
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]

        changes = compute_jira_diff(current, previous)

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 0

    def test_diff_users_uses_account_id_when_no_display_name(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "is_external": False},
        ]
        previous = _empty_jira_data()

        changes = compute_jira_diff(current, previous)
        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert new_users[0]["subject_label"] == "abc1"


class TestAdminDiff:
    def test_diff_admins_added(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        current["group_members"] = {
            "jira-administrators": [{"account_id": "abc1"}],
        }
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        previous["group_members"] = {}

        changes = compute_jira_diff(current, previous)

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 1
        assert role_changes[0]["subject_id"] == "abc1"
        assert role_changes[0]["subject_label"] == "Alice"
        assert role_changes[0]["current_value"] == {"is_admin": True}
        assert role_changes[0]["previous_value"] == {"is_admin": False}

    def test_diff_admins_removed(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        current["group_members"] = {}
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        previous["group_members"] = {
            "site-admins": [{"account_id": "abc1"}],
        }

        changes = compute_jira_diff(current, previous)

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 1
        assert role_changes[0]["subject_id"] == "abc1"
        assert role_changes[0]["current_value"] == {"is_admin": False}
        assert role_changes[0]["previous_value"] == {"is_admin": True}

    def test_diff_admins_no_changes(self) -> None:
        data = _empty_jira_data()
        data["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]
        data["group_members"] = {
            "jira-administrators": [{"account_id": "abc1"}],
        }

        changes = compute_jira_diff(data, data)

        role_changes = [c for c in changes if c["change_type"] == "role_change"]
        assert len(role_changes) == 0


class TestExternalDiff:
    def test_diff_externals_new(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "ext1", "display_name": "Vendor A", "is_external": True},
        ]
        previous = _empty_jira_data()

        changes = compute_jira_diff(current, previous)

        externals = [c for c in changes if c["change_type"] == "new_external"]
        assert len(externals) == 1
        assert externals[0]["subject_id"] == "ext1"
        assert externals[0]["subject_label"] == "Vendor A"
        assert externals[0]["subject_type"] == "user"
        assert externals[0]["current_value"] == {"account_id": "ext1"}
        assert externals[0]["previous_value"] is None

    def test_diff_externals_removed(self) -> None:
        current = _empty_jira_data()
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "ext1", "display_name": "Vendor A", "is_external": True},
        ]

        changes = compute_jira_diff(current, previous)

        removed = [c for c in changes if c["change_type"] == "removed_external"]
        assert len(removed) == 1
        assert removed[0]["subject_id"] == "ext1"
        assert removed[0]["previous_value"] == {"account_id": "ext1"}
        assert removed[0]["current_value"] is None

    def test_diff_externals_no_changes(self) -> None:
        data = _empty_jira_data()
        data["users"] = [
            {"account_id": "ext1", "display_name": "Vendor A", "is_external": True},
        ]

        changes = compute_jira_diff(data, data)

        ext_changes = [
            c for c in changes
            if c["change_type"] in ("new_external", "removed_external")
        ]
        assert len(ext_changes) == 0


class TestGroupMemberDiff:
    def test_diff_group_members_added(self) -> None:
        current = _empty_jira_data()
        current["groups"] = [{"name": "developers"}]
        current["group_members"] = {
            "developers": [{"account_id": "abc1"}, {"account_id": "abc2"}],
        }
        previous = _empty_jira_data()
        previous["groups"] = [{"name": "developers"}]
        previous["group_members"] = {
            "developers": [{"account_id": "abc1"}],
        }

        changes = compute_jira_diff(current, previous)

        membership = [
            c for c in changes if c["change_type"] == "group_membership_change"
        ]
        assert len(membership) == 1
        assert membership[0]["subject_type"] == "group"
        assert membership[0]["subject_id"] == "developers"
        assert membership[0]["subject_label"] == "developers"
        assert "abc2" in membership[0]["current_value"]["added"]
        assert membership[0]["current_value"]["removed"] == []

    def test_diff_group_members_removed(self) -> None:
        current = _empty_jira_data()
        current["groups"] = [{"name": "developers"}]
        current["group_members"] = {
            "developers": [{"account_id": "abc1"}],
        }
        previous = _empty_jira_data()
        previous["groups"] = [{"name": "developers"}]
        previous["group_members"] = {
            "developers": [{"account_id": "abc1"}, {"account_id": "abc2"}],
        }

        changes = compute_jira_diff(current, previous)

        membership = [
            c for c in changes if c["change_type"] == "group_membership_change"
        ]
        assert len(membership) == 1
        assert "abc2" in membership[0]["current_value"]["removed"]
        assert membership[0]["current_value"]["added"] == []

    def test_diff_group_members_no_changes(self) -> None:
        data = _empty_jira_data()
        data["groups"] = [{"name": "developers"}]
        data["group_members"] = {
            "developers": [{"account_id": "abc1"}, {"account_id": "abc2"}],
        }

        changes = compute_jira_diff(data, data)

        membership = [
            c for c in changes if c["change_type"] == "group_membership_change"
        ]
        assert len(membership) == 0


class TestComputeDiffDispatch:
    def test_compute_diff_dispatch_jira(self) -> None:
        current = _empty_jira_data()
        current["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
            {"account_id": "abc2", "display_name": "Bob", "is_external": False},
        ]
        previous = _empty_jira_data()
        previous["users"] = [
            {"account_id": "abc1", "display_name": "Alice", "is_external": False},
        ]

        changes = compute_diff(current, previous, domain="", provider="jira")

        new_users = [c for c in changes if c["change_type"] == "new_user"]
        assert len(new_users) == 1
        assert new_users[0]["subject_id"] == "abc2"


class TestIntegration:
    def test_compute_jira_diff_integration(self) -> None:
        """Full diff with all change types simultaneously."""
        previous = {
            "users": [
                {"account_id": "abc1", "display_name": "Alice", "is_external": False},
                {"account_id": "abc3", "display_name": "Charlie", "is_external": False},
                {"account_id": "ext1", "display_name": "Old Vendor", "is_external": True},
            ],
            "groups": [{"name": "developers"}],
            "group_members": {
                "jira-administrators": [{"account_id": "abc1"}],
                "developers": [
                    {"account_id": "abc1"},
                    {"account_id": "abc3"},
                ],
            },
        }
        current = {
            "users": [
                {"account_id": "abc1", "display_name": "Alice", "is_external": False},
                {"account_id": "abc2", "display_name": "Bob", "is_external": False},
                {"account_id": "ext2", "display_name": "New Vendor", "is_external": True},
            ],
            "groups": [{"name": "developers"}],
            "group_members": {
                "jira-administrators": [{"account_id": "abc2"}],
                "developers": [
                    {"account_id": "abc1"},
                    {"account_id": "abc2"},
                ],
            },
        }

        changes = compute_jira_diff(current, previous)
        change_types = [c["change_type"] for c in changes]

        assert "new_user" in change_types
        assert "removed_user" in change_types
        assert "role_change" in change_types
        assert "new_external" in change_types
        assert "removed_external" in change_types
        assert "group_membership_change" in change_types

    def test_build_diff_summary_with_jira_types(self) -> None:
        changes = [
            {
                "change_type": "new_user",
                "subject_type": "user",
                "subject_id": "abc2",
            },
            {
                "change_type": "removed_external",
                "subject_type": "user",
                "subject_id": "ext1",
            },
            {
                "change_type": "group_membership_change",
                "subject_type": "group",
                "subject_id": "developers",
            },
        ]

        summary = build_diff_summary(changes)

        assert summary["total_changes"] == 3
        assert summary["new_user"] == 1
        assert summary["removed_external"] == 1
        assert summary["group_membership_change"] == 1
        assert summary["removed_user"] == 0
        assert summary["role_change"] == 0
        assert summary["new_external"] == 0
